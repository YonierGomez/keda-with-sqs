#!/usr/bin/env python3
"""
Script idempotente para crear/verificar los recursos AWS necesarios para KEDA + SQS.

Recursos gestionados:
  - Cola SQS principal con Dead Letter Queue
  - Política IAM para acceso a SQS
  - IAM Service Account (IRSA) via eksctl
  - Permissions Boundary en el rol IAM

Tolerante a fallos: si un recurso ya existe, se omite sin error.
Requiere: boto3, eksctl (para el service account)

Uso:
  python3 setup_aws_resources.py [--dry-run]
  CLUSTER_NAME=mi-cluster K8S_NAMESPACE=default python3 setup_aws_resources.py
"""

import boto3
import json
import subprocess
import os
import sys
import argparse
from botocore.exceptions import ClientError, BotoCoreError

# ─── Configuración ────────────────────────────────────────────────────────────
AWS_REGION           = os.getenv("AWS_REGION", "us-east-1")
QUEUE_NAME           = os.getenv("QUEUE_NAME", "keda-with-sqs")
DLQ_NAME             = os.getenv("DLQ_NAME", "keda-with-sqs-dlq")
POLICY_NAME          = os.getenv("POLICY_NAME", "keda-with-sqs-policy")
ROLE_NAME            = os.getenv("ROLE_NAME", "keda-with-sqs-role")
CLUSTER_NAME         = os.getenv("CLUSTER_NAME", "")
NAMESPACE            = os.getenv("K8S_NAMESPACE", "default")
SERVICE_ACCOUNT_NAME = os.getenv("SERVICE_ACCOUNT_NAME", "keda-sqs-sa")
PERMISSIONS_BOUNDARY = os.getenv("PERMISSIONS_BOUNDARY", "Lz-Governance-Boundary")

# ─── Helpers de logging ───────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

def section(title: str) -> None:
    print(f"\n{CYAN}{'─' * 55}")
    print(f"  {title}")
    print(f"{'─' * 55}{RESET}")

def ok(msg: str)   -> None: print(f"{GREEN}  [✓] {msg}{RESET}")
def skip(msg: str) -> None: print(f"{YELLOW}  [~] {msg}{RESET}")
def err(msg: str)  -> None: print(f"{RED}  [✗] {msg}{RESET}")
def info(msg: str) -> None: print(f"      {msg}")


# ─── Paso 0: Obtener Account ID ───────────────────────────────────────────────
def get_account_id() -> str:
    sts = boto3.client("sts", region_name=AWS_REGION)
    account_id = sts.get_caller_identity()["Account"]
    ok(f"AWS Account ID: {account_id}  |  Region: {AWS_REGION}")
    return account_id


# ─── Paso 1: Dead Letter Queue ────────────────────────────────────────────────
def create_dlq(sqs: object, dry_run: bool) -> str:
    section(f"Cola Dead Letter Queue: {DLQ_NAME}")

    if dry_run:
        skip("dry-run: se omitiría la creación de la DLQ")
        return f"https://sqs.{AWS_REGION}.amazonaws.com/000000000000/{DLQ_NAME}"

    try:
        resp = sqs.create_queue(
            QueueName=DLQ_NAME,
            Attributes={
                "DelaySeconds": "0",
                "MaximumMessageSize": "262144",
                "MessageRetentionPeriod": "345600",
                "ReceiveMessageWaitTimeSeconds": "0",
                "VisibilityTimeout": "30",
            },
        )
        url = resp["QueueUrl"]
        ok(f"DLQ creada: {url}")
        return url
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "QueueAlreadyExists":
            url = sqs.get_queue_url(QueueName=DLQ_NAME)["QueueUrl"]
            skip(f"DLQ ya existe: {url}")
            return url
        err(f"Error creando DLQ: {exc}")
        raise


# ─── Paso 2: Cola principal SQS ───────────────────────────────────────────────
def create_main_queue(sqs: object, dlq_url: str, dry_run: bool) -> str:
    section(f"Cola principal SQS: {QUEUE_NAME}")

    if dry_run:
        skip("dry-run: se omitiría la creación de la cola principal")
        return f"https://sqs.{AWS_REGION}.amazonaws.com/000000000000/{QUEUE_NAME}"

    dlq_arn = sqs.get_queue_attributes(
        QueueUrl=dlq_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    info(f"DLQ ARN: {dlq_arn}")

    redrive = json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "5"})

    try:
        resp = sqs.create_queue(
            QueueName=QUEUE_NAME,
            Attributes={
                "DelaySeconds": "0",
                "MaximumMessageSize": "262144",
                "MessageRetentionPeriod": "345600",
                "ReceiveMessageWaitTimeSeconds": "0",
                "VisibilityTimeout": "30",
                "RedrivePolicy": redrive,
            },
        )
        url = resp["QueueUrl"]
        ok(f"Cola principal creada: {url}")
        return url
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "QueueAlreadyExists":
            url = sqs.get_queue_url(QueueName=QUEUE_NAME)["QueueUrl"]
            skip(f"Cola principal ya existe: {url}")
            return url
        err(f"Error creando cola principal: {exc}")
        raise


# ─── Paso 3: Política IAM ─────────────────────────────────────────────────────
def create_iam_policy(iam: object, account_id: str, dry_run: bool) -> str:
    section(f"Política IAM: {POLICY_NAME}")

    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "sqs:GetQueueUrl",
                    "sqs:GetQueueAttributes",
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                ],
                "Resource": f"arn:aws:sqs:{AWS_REGION}:{account_id}:{QUEUE_NAME}",
            }
        ],
    }
    policy_arn = f"arn:aws:iam::{account_id}:policy/{POLICY_NAME}"

    if dry_run:
        skip(f"dry-run: se omitiría la creación de la política: {policy_arn}")
        return policy_arn

    try:
        iam.create_policy(
            PolicyName=POLICY_NAME,
            PolicyDocument=json.dumps(policy_document),
            Description="Política de acceso a SQS para KEDA",
        )
        ok(f"Política creada: {policy_arn}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "EntityAlreadyExists":
            skip(f"Política ya existe: {policy_arn}")
        else:
            err(f"Error creando política: {exc}")
            raise

    return policy_arn


# ─── Paso 4: IAM Service Account (IRSA via eksctl) ───────────────────────────
def create_service_account(account_id: str, policy_arn: str, dry_run: bool) -> None:
    section(f"IAM Service Account (IRSA): {SERVICE_ACCOUNT_NAME}")

    if not CLUSTER_NAME:
        skip("CLUSTER_NAME no definido — omitiendo creación de service account.")
        info("Exporta CLUSTER_NAME=<nombre-del-cluster> para ejecutar este paso.")
        return

    cmd = [
        "eksctl", "create", "iamserviceaccount",
        f"--cluster={CLUSTER_NAME}",
        f"--namespace={NAMESPACE}",
        f"--name={SERVICE_ACCOUNT_NAME}",
        f"--role-name={ROLE_NAME}",
        f"--attach-policy-arn={policy_arn}",
        "--override-existing-serviceaccounts",
        "--approve",
    ]
    info(f"Comando: {' '.join(cmd)}")

    if dry_run:
        skip("dry-run: se omitiría la ejecución del comando eksctl")
        return

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        ok(f"Service account '{SERVICE_ACCOUNT_NAME}' creado/actualizado")
        if result.stdout:
            info(result.stdout.strip())
    except subprocess.CalledProcessError as exc:
        stderr_lower = exc.stderr.lower()
        if "alreadyexists" in stderr_lower or "already exists" in stderr_lower:
            skip(f"Service account '{SERVICE_ACCOUNT_NAME}' ya existe")
        else:
            err(f"Error ejecutando eksctl:\n{exc.stderr}")
            raise
    except FileNotFoundError:
        err("eksctl no encontrado. Instálalo para continuar con este paso.")
        info("https://eksctl.io/installation/")
        sys.exit(1)


# ─── Paso 5: Permissions Boundary ────────────────────────────────────────────
def add_permissions_boundary(iam: object, account_id: str, dry_run: bool) -> None:
    section(f"Permissions Boundary en rol: {ROLE_NAME}")

    boundary_arn = f"arn:aws:iam::{account_id}:policy/{PERMISSIONS_BOUNDARY}"
    info(f"Boundary ARN: {boundary_arn}")

    # Verificar que el rol existe
    try:
        iam.get_role(RoleName=ROLE_NAME)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchEntity":
            skip(f"Rol '{ROLE_NAME}' no encontrado — omitiendo permissions boundary.")
            return
        raise

    if dry_run:
        skip("dry-run: se omitiría la asignación del permissions boundary")
        return

    try:
        iam.put_role_permissions_boundary(
            RoleName=ROLE_NAME,
            PermissionsBoundary=boundary_arn,
        )
        ok(f"Permissions boundary asignado al rol '{ROLE_NAME}'")
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "NoSuchEntity":
            skip(f"Boundary policy no encontrada: {boundary_arn} — omitiendo.")
        else:
            err(f"Error asignando permissions boundary: {exc}")
            raise


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crea recursos AWS para KEDA + SQS de forma idempotente."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra los pasos sin ejecutar cambios reales en AWS.",
    )
    args = parser.parse_args()

    print(f"\n{'═' * 55}")
    print("  KEDA + SQS — Creación de recursos AWS")
    if args.dry_run:
        print(f"  {YELLOW}MODO DRY-RUN — no se harán cambios reales{RESET}")
    print(f"{'═' * 55}")

    try:
        account_id  = get_account_id()
        sqs_client  = boto3.client("sqs", region_name=AWS_REGION)
        iam_client  = boto3.client("iam")

        dlq_url     = create_dlq(sqs_client, args.dry_run)
        queue_url   = create_main_queue(sqs_client, dlq_url, args.dry_run)
        policy_arn  = create_iam_policy(iam_client, account_id, args.dry_run)
        create_service_account(account_id, policy_arn, args.dry_run)
        add_permissions_boundary(iam_client, account_id, args.dry_run)

        print(f"\n{GREEN}{'═' * 55}")
        print("  Todos los recursos fueron creados/verificados.")
        print(f"  Queue URL : {queue_url}")
        print(f"  Policy ARN: {policy_arn}")
        print(f"{'═' * 55}{RESET}\n")

    except (ClientError, BotoCoreError) as exc:
        err(f"Error AWS: {exc}")
        sys.exit(1)
    except Exception as exc:
        err(f"Error inesperado: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
