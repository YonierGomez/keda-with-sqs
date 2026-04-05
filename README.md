# KEDA with SQS — Pod Autoscaling on EKS

[![GitHub Stars](https://img.shields.io/github/stars/YonierGomez/keda-with-sqs?style=flat-square&logo=github&color=yellow)](https://github.com/YonierGomez/keda-with-sqs/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/YonierGomez/keda-with-sqs?style=flat-square&logo=github)](https://github.com/YonierGomez/keda-with-sqs/network/members)
[![Docker Pulls](https://img.shields.io/docker/pulls/yoniergomez/keda-with-sqs?style=flat-square&logo=docker&color=blue)](https://hub.docker.com/r/yoniergomez/keda-with-sqs)
[![Docker Image Size](https://img.shields.io/docker/image-size/yoniergomez/keda-with-sqs/latest?style=flat-square&logo=docker)](https://hub.docker.com/r/yoniergomez/keda-with-sqs)
[![CI](https://img.shields.io/github/actions/workflow/status/YonierGomez/keda-with-sqs/docker-image.yml?branch=main&style=flat-square&logo=githubactions&label=CI)](https://github.com/YonierGomez/keda-with-sqs/actions/workflows/docker-image.yml)
[![License](https://img.shields.io/github/license/YonierGomez/keda-with-sqs?style=flat-square)](LICENSE)

![Node.js](https://img.shields.io/badge/Node.js-alpine-339933?style=flat-square&logo=node.js&logoColor=white)
![AWS SQS](https://img.shields.io/badge/AWS-SQS-FF9900?style=flat-square&logo=amazonsqs&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-EKS-326CE5?style=flat-square&logo=kubernetes&logoColor=white)
![KEDA](https://img.shields.io/badge/KEDA-autoscaling-00bcd4?style=flat-square&logo=keda&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-multi--arch-2496ED?style=flat-square&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-boto3-3776AB?style=flat-square&logo=python&logoColor=white)

Lab for scaling pods in Kubernetes (EKS) based on messages in an **AWS SQS** queue using **KEDA** (Kubernetes Event-Driven Autoscaling).

---

## Architecture

```
┌──────────────┐     messages     ┌─────────────┐     metrics      ┌──────────────┐
│  Producer    │ ──────────────►  │  AWS SQS    │ ──────────────►  │    KEDA      │
│  (enviar.js) │                  │  Queue      │                  │  ScaledObject│
└──────────────┘                  └─────────────┘                  └──────┬───────┘
                                                                          │ scales
                                                                   ┌──────▼───────┐
                                                                   │  Deployment  │
                                                                   │  (app.js)    │
                                                                   └──────────────┘
```

---

## Project structure

```
keda-with-sqs/
├── app.js                         # SQS consumer (Node.js)
├── enviar.js                      # Test message producer
├── dockerfile                     # Docker image for the consumer
├── package.json
├── .github/
│   └── workflows/
│       └── docker-image.yml       # CI/CD: multi-arch build and push to Docker Hub
├── app-k8s/
│   ├── app-k8s.yaml               # EKS Deployment manifest
│   └── scale.yaml                 # KEDA ScaledObject manifest
├── aws_resources/
│   ├── setup_aws_resources.py     # Idempotent Python script to reconcile AWS resources
│   ├── sqs.json                   # IAM policy document
│   └── sqs-stack.yaml             # CloudFormation stack (reference)
└── send_message_sqs/
    └── send_message.sh            # Script to send test messages to SQS
```

---

## Docker image

The image is published on Docker Hub:

**[yoniergomez/keda-with-sqs](https://hub.docker.com/r/yoniergomez/keda-with-sqs)**

```bash
docker pull yoniergomez/keda-with-sqs:latest
```

### Run locally

```bash
docker run -e QUEUE_URL="https://sqs.us-east-1.amazonaws.com/<ACCOUNT_ID>/<QUEUE_NAME>" \
  yoniergomez/keda-with-sqs:latest
```

---

## AWS Resources

### Python script (recommended)

`aws_resources/setup_aws_resources.py` is a **reconciliation script**: it creates each resource if it does not exist, and updates it to match the desired configuration if it already exists. Running it multiple times is safe — the end state is always the same.

#### Managed resources

| Resource              | Default name               |
|-----------------------|----------------------------|
| SQS Queue             | `keda-with-sqs`            |
| SQS Dead Letter Queue | `keda-with-sqs-dlq`        |
| IAM Policy            | `keda-with-sqs-policy`     |
| IAM Role (IRSA)       | `keda-with-sqs-role`       |
| Kubernetes SA         | `keda-sqs-sa`              |

#### Install dependencies

```bash
pip install boto3
```

#### Usage

```bash
# Dry-run (shows steps without making real changes)
python3 aws_resources/setup_aws_resources.py --dry-run

# Real execution (requires AWS credentials configured)
export CLUSTER_NAME="my-eks-cluster"
export K8S_NAMESPACE="default"
python3 aws_resources/setup_aws_resources.py
```

#### Environment variables

| Variable               | Default                    | Description                        |
|------------------------|----------------------------|------------------------------------|
| `AWS_REGION`           | `us-east-1`                | AWS region                         |
| `QUEUE_NAME`           | `keda-with-sqs`            | SQS queue name                     |
| `DLQ_NAME`             | `keda-with-sqs-dlq`        | Dead Letter Queue name             |
| `POLICY_NAME`          | `keda-with-sqs-policy`     | IAM policy name                    |
| `ROLE_NAME`            | `keda-with-sqs-role`       | IAM role name                      |
| `CLUSTER_NAME`         | *(empty — step skipped)*   | EKS cluster name                   |
| `K8S_NAMESPACE`        | `default`                  | Kubernetes namespace               |
| `SERVICE_ACCOUNT_NAME` | `keda-sqs-sa`              | Kubernetes Service Account name    |
| `PERMISSIONS_BOUNDARY` | `Lz-Governance-Boundary`   | Permissions boundary policy name   |

---

### CloudFormation (reference)

```bash
aws cloudformation deploy \
  --template-file aws_resources/sqs-stack.yaml \
  --stack-name keda-with-sqs \
  --capabilities CAPABILITY_IAM
```

---

## Deploy on EKS

### 1. Prerequisites

- EKS cluster with KEDA installed
- IRSA configured (service account with IAM role)

### 2. Install KEDA

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda --namespace keda --create-namespace
```

### 3. Apply manifests

> Update the image in `app-k8s/app-k8s.yaml` to `yoniergomez/keda-with-sqs:latest` before applying.

```bash
kubectl apply -f app-k8s/app-k8s.yaml
kubectl apply -f app-k8s/scale.yaml
```

### 4. Send test messages

```bash
bash send_message_sqs/send_message.sh
```

---

## What is KEDA?

KEDA is a lightweight component that adds event-driven scaling to any Kubernetes cluster, extending the HPA (Horizontal Pod Autoscaler) for external event sources like SQS, Kafka, or Azure Service Bus. It only activates on deployments where a `ScaledObject` is declared.

**Lab configuration:**

| Parameter          | Value | Description                                      |
|--------------------|-------|--------------------------------------------------|
| `minReplicaCount`  | `0`   | Pods scale to zero when the queue is empty       |
| `maxReplicaCount`  | `10`  | Scale up to 10 pods under load                   |
| `queueLength`      | `5`   | One pod per 5 messages in the queue              |
| `pollingInterval`  | `30s` | How often KEDA checks the queue                  |
| `cooldownPeriod`   | `10s` | Wait time before scaling down                    |
