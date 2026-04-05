# KEDA with SQS — Autoscaling de Pods en EKS

Laboratorio para escalar pods en Kubernetes (EKS) basado en mensajes en una cola **AWS SQS** usando **KEDA** (Kubernetes Event-Driven Autoscaling).

---

## Arquitectura

```
┌──────────────┐     mensajes     ┌─────────────┐     métricas     ┌──────────────┐
│  Productor   │ ──────────────►  │  AWS SQS    │ ──────────────►  │    KEDA      │
│  (enviar.js) │                  │  Queue      │                  │  ScaledObject│
└──────────────┘                  └─────────────┘                  └──────┬───────┘
                                                                          │ escala
                                                                   ┌──────▼───────┐
                                                                   │  Deployment  │
                                                                   │  (app.js)    │
                                                                   └──────────────┘
```

---

## Estructura del proyecto

```
keda-with-sqs/
├── app.js                         # Consumidor SQS (Node.js)
├── enviar.js                      # Productor de mensajes de prueba
├── dockerfile                     # Imagen Docker del consumidor
├── package.json
├── .github/
│   └── workflows/
│       └── docker-publish.yml     # CI/CD: build y push a Docker Hub
├── app-k8s/
│   ├── app-k8s.yaml               # Deployment en EKS
│   └── scale.yaml                 # ScaledObject de KEDA
├── aws_resources/
│   ├── setup_aws_resources.py     # Script Python idempotente para crear recursos AWS
│   ├── sqs.json                   # Documento de política IAM
│   └── sqs-stack.yaml             # Stack CloudFormation (referencia)
└── send_message_sqs/
    └── send_message.sh            # Script para enviar mensajes de prueba a SQS
```

---

## Imagen Docker

La imagen está publicada en Docker Hub:

**[yoniergomez/keda-with-sqs](https://hub.docker.com/r/yoniergomez/keda-with-sqs)**

```bash
docker pull yoniergomez/keda-with-sqs:latest
```

### Ejecutar localmente

```bash
docker run -e QUEUE_URL="https://sqs.us-east-1.amazonaws.com/<ACCOUNT_ID>/<QUEUE_NAME>" \
  yoniergomez/keda-with-sqs:latest
```

---

## CI/CD — GitHub Actions

El workflow `.github/workflows/docker-publish.yml` hace build y push automático a Docker Hub cada vez que se hace push a `main` con cambios en `app.js`, `package.json` o `dockerfile`.

### Secrets requeridos en GitHub

| Secret     | Descripción                    |
|------------|--------------------------------|
| `USER_HUB` | Usuario de Docker Hub          |
| `PASS_HUB` | Token/contraseña de Docker Hub |

### Tags generados automáticamente

- `yoniergomez/keda-with-sqs:latest` — en cada push a `main`
- `yoniergomez/keda-with-sqs:<sha-corto>` — por commit

---

## Recursos AWS

### Opción A — Script Python (recomendado)

El script `aws_resources/setup_aws_resources.py` es **idempotente**: si un recurso ya existe lo omite sin error.

#### Recursos que gestiona

| Recurso               | Nombre por defecto         |
|-----------------------|----------------------------|
| SQS Cola              | `keda-with-sqs`            |
| SQS Dead Letter Queue | `keda-with-sqs-dlq`        |
| Política IAM          | `keda-with-sqs-policy`     |
| Rol IAM (IRSA)        | `keda-with-sqs-role`       |
| Service Account K8s   | `keda-sqs-sa`              |

#### Instalación de dependencias

```bash
pip install boto3
```

#### Ejecución

```bash
# Modo dry-run (muestra pasos sin hacer cambios)
python3 aws_resources/setup_aws_resources.py --dry-run

# Ejecución real (requiere credenciales AWS configuradas)
export CLUSTER_NAME="mi-eks-cluster"
export K8S_NAMESPACE="default"
python3 aws_resources/setup_aws_resources.py
```

#### Variables de entorno disponibles

| Variable               | Default                    | Descripción                        |
|------------------------|----------------------------|------------------------------------|
| `AWS_REGION`           | `us-east-1`                | Región de AWS                      |
| `QUEUE_NAME`           | `keda-with-sqs`            | Nombre de la cola SQS              |
| `DLQ_NAME`             | `keda-with-sqs-dlq`        | Nombre de la cola DLQ              |
| `POLICY_NAME`          | `keda-with-sqs-policy`     | Nombre de la política IAM          |
| `ROLE_NAME`            | `keda-with-sqs-role`       | Nombre del rol IAM                 |
| `CLUSTER_NAME`         | *(vacío — omite paso)*     | Nombre del cluster EKS             |
| `K8S_NAMESPACE`        | `default`                  | Namespace en Kubernetes            |
| `SERVICE_ACCOUNT_NAME` | `keda-sqs-sa`              | Nombre del Service Account         |
| `PERMISSIONS_BOUNDARY` | `Lz-Governance-Boundary`   | Nombre del permissions boundary    |

---

### Opción B — CloudFormation (referencia)

```bash
aws cloudformation deploy \
  --template-file aws_resources/sqs-stack.yaml \
  --stack-name keda-with-sqs \
  --capabilities CAPABILITY_IAM
```

---

## Despliegue en EKS

### 1. Prerequisitos

- Cluster EKS con KEDA instalado
- IRSA configurado (service account con rol IAM)

### 2. Instalar KEDA

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda --namespace keda --create-namespace
```

### 3. Aplicar manifiestos

> Actualiza la imagen en `app-k8s/app-k8s.yaml` con `yoniergomez/keda-with-sqs:latest` antes de aplicar.

```bash
kubectl apply -f app-k8s/app-k8s.yaml
kubectl apply -f app-k8s/scale.yaml
```

### 4. Enviar mensajes de prueba

```bash
bash send_message_sqs/send_message.sh
```

---

## ¿Qué es KEDA?

KEDA es un componente ligero que se añade a cualquier clúster Kubernetes y extiende el HPA (Horizontal Pod Autoscaler) para escalar en base a eventos externos (colas SQS, Kafka, Azure Service Bus, etc.). Solo se activa en los deployments donde se declara un `ScaledObject`.

**Comportamiento de este laboratorio:**

| Parámetro          | Valor | Descripción                                      |
|--------------------|-------|--------------------------------------------------|
| `minReplicaCount`  | `0`   | Los pods se apagan cuando no hay mensajes        |
| `maxReplicaCount`  | `10`  | Escala hasta 10 pods bajo carga                  |
| `queueLength`      | `5`   | Un pod por cada 5 mensajes en la cola            |
| `pollingInterval`  | `30s` | Frecuencia de revisión de la cola                |
| `cooldownPeriod`   | `10s` | Espera antes de desescalar                       |
