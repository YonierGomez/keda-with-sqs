#!/usr/bin/env python3
"""
Idempotent script to reconcile the AWS resources required for KEDA + SQS.

Managed resources:
  - SQS main queue with Dead Letter Queue
  - IAM policy for SQS access
  - IAM Service Account (IRSA) via eksctl
  - Permissions Boundary on the IAM role

Behavior: each resource is created if it does not exist, or updated to match
the desired configuration if it already exists. Running this script multiple
times is safe — the end state is always the same.

Requires: boto3, eksctl (for the service account step)

Usage:
  python3 setup_aws_resources.py [--dry-run]
  CLUSTER_NAME=my-cluster K8S_NAMESPACE=default python3 setup_aws_resources.py
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


# ─── Step 0: Get Account ID ──────────────────────────────────────────────────
def get_account_id() -> str:
    sts = boto3.client("sts", region_name=AWS_REGION)
    account_id = sts.get_caller_identity()["Account"]
    ok(f"AWS Account ID: {account_id}  |  Region: {AWS_REGION}")
    return account_id


DESIRED_QUEUE_ATTRS = {
    "DelaySeconds": "0",
    "MaximumMessageSize": "262144",
    "MessageRetentionPeriod": "345600",
    "ReceiveMessageWaitTimeSeconds": "0",
    "VisibilityTimeout": "30",
}


def _enforce_queue_attrs(sqs: object, url: str, attrs: dict) -> None:
    """Compare current queue attributes against desired and update if different."""
    mutable_keys = {
        "DelaySeconds", "MaximumMessageSize", "MessageRetentionPeriod",
        "ReceiveMessageWaitTimeSeconds", "VisibilityTimeout", "RedrivePolicy",
    }
    current = sqs.get_queue_attributes(
        QueueUrl=url, AttributeNames=list(attrs.keys())
    )["Attributes"]

    diff = {
        k: v for k, v in attrs.items()
        if k in mutable_keys and current.get(k) != v
    }
    if diff:
        sqs.set_queue_attributes(QueueUrl=url, Attributes=diff)
        info(f"Attributes updated: {list(diff.keys())}")
    else:
        info("Attributes already match desired state — no changes needed.")


# ─── Step 1: Dead Letter Queue ────────────────────────────────────────────────
def create_dlq(sqs: object, dry_run: bool) -> str:
    section(f"Dead Letter Queue: {DLQ_NAME}")

    if dry_run:
        skip("dry-run: DLQ creation would be skipped")
        return f"https://sqs.{AWS_REGION}.amazonaws.com/000000000000/{DLQ_NAME}"

    try:
        resp = sqs.create_queue(
            QueueName=DLQ_NAME,
            Attributes=DESIRED_QUEUE_ATTRS,
        )
        url = resp["QueueUrl"]
        ok(f"DLQ created: {url}")
        return url
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "QueueAlreadyExists":
            url = sqs.get_queue_url(QueueName=DLQ_NAME)["QueueUrl"]
            info(f"DLQ already exists: {url} — enforcing desired attributes...")
            _enforce_queue_attrs(sqs, url, DESIRED_QUEUE_ATTRS)
            ok(f"DLQ reconciled: {url}")
            return url
        err(f"Error creating DLQ: {exc}")
        raise


# ─── Step 2: Main SQS queue ──────────────────────────────────────────────────
def create_main_queue(sqs: object, dlq_url: str, dry_run: bool) -> str:
    section(f"Main SQS Queue: {QUEUE_NAME}")

    if dry_run:
        skip("dry-run: main queue creation would be skipped")
        return f"https://sqs.{AWS_REGION}.amazonaws.com/000000000000/{QUEUE_NAME}"

    dlq_arn = sqs.get_queue_attributes(
        QueueUrl=dlq_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    info(f"DLQ ARN: {dlq_arn}")

    redrive = json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "5"})
    desired_attrs = {**DESIRED_QUEUE_ATTRS, "RedrivePolicy": redrive}

    try:
        resp = sqs.create_queue(
            QueueName=QUEUE_NAME,
            Attributes=desired_attrs,
        )
        url = resp["QueueUrl"]
        ok(f"Main queue created: {url}")
        return url
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "QueueAlreadyExists":
            url = sqs.get_queue_url(QueueName=QUEUE_NAME)["QueueUrl"]
            info(f"Main queue already exists: {url} — enforcing desired attributes...")
            _enforce_queue_attrs(sqs, url, desired_attrs)
            ok(f"Main queue reconciled: {url}")
            return url
        err(f"Error creating main queue: {exc}")
        raise


# ─── Step 3: IAM policy ──────────────────────────────────────────────────────
def create_iam_policy(iam: object, account_id: str, dry_run: bool) -> str:
    section(f"IAM Policy: {POLICY_NAME}")

    desired_document = {
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
        skip(f"dry-run: IAM policy reconciliation would be skipped: {policy_arn}")
        return policy_arn

    try:
        iam.create_policy(
            PolicyName=POLICY_NAME,
            PolicyDocument=json.dumps(desired_document),
            Description="SQS access policy for KEDA",
        )
        ok(f"IAM policy created: {policy_arn}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "EntityAlreadyExists":
            err(f"Error creating IAM policy: {exc}")
            raise

        # Policy exists — compare current default version with desired document
        import urllib.parse
        info(f"Policy already exists: {policy_arn} — comparing document...")
        default_ver = iam.get_policy(PolicyArn=policy_arn)["Policy"]["DefaultVersionId"]
        current_doc_raw = iam.get_policy_version(
            PolicyArn=policy_arn, VersionId=default_ver
        )["PolicyVersion"]["Document"]
        # AWS may return the document already decoded or URL-encoded
        if isinstance(current_doc_raw, str):
            current_doc = json.loads(urllib.parse.unquote(current_doc_raw))
        else:
            current_doc = current_doc_raw

        if json.dumps(current_doc, sort_keys=True) == json.dumps(desired_document, sort_keys=True):
            ok(f"IAM policy document already matches desired state — no changes needed.")
        else:
            # Enforce: create a new version and set it as default
            # IAM allows max 5 versions — delete the oldest non-default one if needed
            versions = iam.list_policy_versions(PolicyArn=policy_arn)["Versions"]
            non_default = [v for v in versions if not v["IsDefaultVersion"]]
            if len(versions) >= 5 and non_default:
                oldest = sorted(non_default, key=lambda v: v["CreateDate"])[0]
                iam.delete_policy_version(PolicyArn=policy_arn, VersionId=oldest["VersionId"])
                info(f"Deleted oldest policy version: {oldest['VersionId']}")
            iam.create_policy_version(
                PolicyArn=policy_arn,
                PolicyDocument=json.dumps(desired_document),
                SetAsDefault=True,
            )
            ok(f"IAM policy document updated to new version.")

    return policy_arn


# ─── Step 4: IAM Service Account (IRSA via eksctl) ──────────────────────────
def create_service_account(account_id: str, policy_arn: str, dry_run: bool) -> None:
    section(f"IAM Service Account (IRSA): {SERVICE_ACCOUNT_NAME}")

    if not CLUSTER_NAME:
        skip("CLUSTER_NAME not set — skipping service account step.")
        info("Export CLUSTER_NAME=<cluster-name> to run this step.")
        return

    # --override-existing-serviceaccounts makes eksctl update if it already exists
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
    info(f"Command: {' '.join(cmd)}")

    if dry_run:
        skip("dry-run: eksctl command would be skipped")
        return

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        ok(f"Service account '{SERVICE_ACCOUNT_NAME}' created/updated")
        if result.stdout:
            info(result.stdout.strip())
    except subprocess.CalledProcessError as exc:
        err(f"eksctl error:\n{exc.stderr}")
        raise
    except FileNotFoundError:
        err("eksctl not found. Install it to run this step.")
        info("https://eksctl.io/installation/")
        sys.exit(1)


# ─── Step 5: Permissions Boundary ───────────────────────────────────────────
def add_permissions_boundary(iam: object, account_id: str, dry_run: bool) -> None:
    section(f"Permissions Boundary on role: {ROLE_NAME}")

    boundary_arn = f"arn:aws:iam::{account_id}:policy/{PERMISSIONS_BOUNDARY}"
    info(f"Boundary ARN: {boundary_arn}")

    # Check the role exists before trying to set the boundary
    try:
        role = iam.get_role(RoleName=ROLE_NAME)["Role"]
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchEntity":
            skip(f"Role '{ROLE_NAME}' not found — skipping permissions boundary.")
            return
        raise

    current_boundary = (role.get("PermissionsBoundary") or {}).get("PermissionsBoundaryArn", "")
    if current_boundary == boundary_arn:
        ok(f"Permissions boundary already set correctly on role '{ROLE_NAME}'.")
        return

    if dry_run:
        skip("dry-run: permissions boundary update would be skipped")
        return

    try:
        iam.put_role_permissions_boundary(
            RoleName=ROLE_NAME,
            PermissionsBoundary=boundary_arn,
        )
        ok(f"Permissions boundary set on role '{ROLE_NAME}'.")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchEntity":
            skip(f"Boundary policy not found: {boundary_arn} — skipping.")
        else:
            err(f"Error setting permissions boundary: {exc}")
            raise


# ─── Main ────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconcile AWS resources for KEDA + SQS (idempotent)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show steps without making real changes in AWS.",
    )
    args = parser.parse_args()

    print(f"\n{'═' * 55}")
    print("  KEDA + SQS — AWS Resource Reconciliation")
    if args.dry_run:
        print(f"  {YELLOW}DRY-RUN MODE — no real changes will be made{RESET}")
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
        print("  All resources reconciled successfully.")
        print(f"  Queue URL : {queue_url}")
        print(f"  Policy ARN: {policy_arn}")
        print(f"{'═' * 55}{RESET}\n")

    except (ClientError, BotoCoreError) as exc:
        err(f"AWS error: {exc}")
        sys.exit(1)
    except Exception as exc:
        err(f"Unexpected error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
