SQS Consumer App built with Node.js to read messages from an SQS queue and display them.
======================

## Quick reference
* [What is Amazon SQS?](#what-is-amazon-sqs)
* [What does this image do?](#what-does-this-image-do)
* [How to use this image](#how-to-use-this-image)
* [Supported architectures](#supported-architectures)
* [Environment variables](#environment-variables)
* [Running on Raspberry Pi](#running-on-raspberry-pi)
* [Visit my website](#visit-my-website)


## What is Amazon SQS?

Amazon Simple Queue Service (Amazon SQS) is a fully managed message queuing service that enables you to decouple and scale microservices, distributed systems, and serverless applications.

Messages sent through Amazon SQS are stored in a queue until they are processed or deleted. The service can transmit any volume of data without losing messages or requiring additional services. It integrates with other AWS services to build scalable and reliable solutions.

Amazon SQS offers two types of queues: standard queues and FIFO (First-In-First-Out) queues. Standard queues offer at-least-once delivery, while FIFO queues offer exactly-once delivery.

![sqs](https://d1.awsstatic.com/legal/AmazonMessaging_SQS_SNS/product-page-diagram_Amazon-SQS%402x.6df419be87198e0f8b0c8151eceac65584db78ea.png)

## What does this image do?

This app is built with Node.js and acts as an **SQS consumer**: it polls a queue, reads incoming messages, and prints them to stdout.


## How to use this image

You can use either the Docker CLI or Docker Compose.

### Required

You must pass the `-e QUEUE_URL=<YOUR_SQS_QUEUE_URL>` environment variable.

### docker-compose (recommended)

```yaml
---
version: '3'
services:
  sqs_consumer:
    image: yoniergomez/keda-with-sqs
    container_name: sqs_consumer
    restart: always
    environment:
      - QUEUE_URL=<YOUR_SQS_QUEUE_URL>  # REQUIRED
```

> Tip: You can replace `environment` with `env_file` and point it to a `.env` file containing the variables.

### docker cli

```bash
docker run --name sqs_consumer \
  -e QUEUE_URL=<YOUR_SQS_QUEUE_URL> \
  -d yoniergomez/keda-with-sqs
```

## Supported architectures

| Architecture | Available | Pull command |
|--------------|-----------|----------------------------------------------|
| x86-64       | ✅        | `docker pull yoniergomez/keda-with-sqs`       |
| arm64        | ✅        | `docker pull yoniergomez/keda-with-sqs`       |

Both architectures are bundled in the same multi-arch manifest — no separate tags needed.

## Environment variables

| Variable      | Required | Description                          |
|---------------|----------|--------------------------------------|
| `QUEUE_URL`   | **yes**  | Full URL of the SQS queue to consume |

## Running on Raspberry Pi

The image supports `linux/arm64` natively, so it works on any Raspberry Pi running a 64-bit OS:

```bash
docker run --name sqs_consumer \
  -e QUEUE_URL=<YOUR_SQS_QUEUE_URL> \
  -d yoniergomez/keda-with-sqs
```

## Visit my website

Check out new content and projects at [https://yonier.com](https://yonier.com)
