# KEDA × SQS — Event-Driven Pod Autoscaling on EKS

Node.js SQS consumer designed to run on **Amazon EKS** and scale automatically with **KEDA** (Kubernetes Event-Driven Autoscaling). When the queue is empty the deployment scales to **zero pods**. As messages arrive, KEDA scales up to **10 replicas** at a rate of one pod per 5 messages.

## Pull

```bash
docker pull yoniergomez/keda-with-sqs:latest
```

## Run

```bash
docker run \
  -e QUEUE_URL="https://sqs.us-east-1.amazonaws.com/<ACCOUNT_ID>/<QUEUE_NAME>" \
  yoniergomez/keda-with-sqs:latest
```

## Environment variables

| Variable    | Required | Description                        |
|-------------|----------|------------------------------------|
| `QUEUE_URL` | yes      | Full SQS queue URL to consume from |

## Tags

| Tag        | Description                    |
|------------|--------------------------------|
| `latest`   | Latest stable build from `main`|
| `<sha>`    | Immutable commit-pinned build  |

## Architectures

- `linux/amd64`
- `linux/arm64`

Built automatically via GitHub Actions on every push to `main`.

## How it works

The container polls the SQS queue every **5 seconds**, processes up to 10 messages per cycle, and deletes them after processing. Authentication to AWS uses **IRSA** (IAM Roles for Service Accounts) — no credentials are stored in the image.

KEDA's `ScaledObject` monitors queue depth and adjusts replicas accordingly:

```
queue depth  →  desired pods
──────────────────────────────
0            →  0  (scale to zero)
1–5          →  1
6–10         →  2
…
46–50        →  10 (max)
```

## Links

- **Source code & docs:** https://github.com/YonierGomez/keda-with-sqs
- **Landing page:** https://yoniergomez.github.io/keda-with-sqs/
- **Author:** https://yonier.com
