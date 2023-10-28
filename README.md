# Escalar pods basado en eventos

### Autoscaling de pods basado en eventos

Para implementar el autoscaling se habilita dentro de la  línea base de EKS la herramienta KEDA (Kubernetes Event Driven  Autoscaling) que me va a permitir escalar basado en eventos en EKS. Esta herramienta no compite con HPA (Horizontal pod autoscaler) sino que  amplia la capacidad para escalar de acuerdo a otro tipo de eventos y  solo aplica para los despliegues donde se habilita su uso.

### ¿Qué es Keda?

Es un componente ligero y de propósito único que puede  añadirse a cualquier clúster de Kubernetes. Funciona junto a los  componentes estándar de Kubernetes, como el HPA horizontal pod  autoscaler y puede ampliar la funcionalidad sin sobrescribirla ni  duplicarla. Con KEDA se pueden asignar explícitamente las aplicaciones  que se deseen utilizar este escalado de por eventos mientras que las  demás aplicaciones siguen funcionando.

Esto hace que sea una opción flexible y segura para ejecutar  junto a cualquier número de otras aplicaciones o marcos de trabajo de  Kubernetes.

## Arquitectura de laboratorio

![SQS](/data/work-bco/keda-role/SQS-APP/SQS.png)

## Cola sqs

Creamos un stack de cloudformation para nuestro servicio de sqs

```yaml
Resources:
  MyQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: yonier-sqs
      DelaySeconds: 0
      MaximumMessageSize: 262144
      MessageRetentionPeriod: 345600
      ReceiveMessageWaitTimeSeconds: 0
      VisibilityTimeout: 30
      RedrivePolicy:
        deadLetterTargetArn: { "Fn::GetAtt" : ["DLQueue", "Arn"] }
        maxReceiveCount: 5
  DLQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: yonier-sqs-dlq
      DelaySeconds: 0
      MaximumMessageSize: 262144
      MessageRetentionPeriod: 345600
      ReceiveMessageWaitTimeSeconds: 0
      VisibilityTimeout: 30
```

## App en nodejs

He creado una app en node js que se encarga de leer los mensajes en una cola de sqs.

### Pasos previos

Creamos un proyecto de nodejs.

```bash
npm init -y

#Instalamos el sdk para sqs
npm install aws-sdk 
```

Esto nos generará nuestro package.json

### App

```javascript
const AWS = require('aws-sdk');

// Configuración de AWS con la región apropiada
AWS.config.update({ region: 'us-east-1' });

// Crear una instancia de SQS
const sqs = new AWS.SQS({ apiVersion: '2012-11-05' });

// URL de la cola de SQS desde la variable de entorno
const queueUrl = process.env.QUEUE_URL;
console.log('Prueba');
console.log(queueUrl);

// Configuración de parámetros para recibir mensajes de la cola
const params = {
  AttributeNames: [
    'All'
  ],
  MaxNumberOfMessages: 10,
  MessageAttributeNames: [
    'All'
  ],
  QueueUrl: queueUrl,
  VisibilityTimeout: 20,
  WaitTimeSeconds: 0
};

// Función para recibir mensajes de la cola de SQS
const receiveSQSMessages = () => {
  sqs.receiveMessage(params, (err, data) => {
    if (err) {
      console.log('Error al recibir mensajes de la cola de SQS:', err);
    } else if (data.Messages) {
      console.log('Mensajes recibidos de la cola de SQS:');
      data.Messages.forEach(message => {
        console.log('Cuerpo del mensaje:', message.Body);
        console.log('Id del mensaje:', message.MessageId);
        console.log('Recibo del mensaje:', message.ReceiptHandle);
        console.log('---');
      });
    } else {
      console.log('No hay mensajes disponibles en la cola de SQS.');
    }
  });
};

// Ejecutar la función cada 5 segundos (puedes ajustar este valor según tus necesidades)
setInterval(receiveSQSMessages, 5000);

```

## Contenerizar app

Creamos un Dockerfile para generar una imagen de docker

```dockerfile
# Usar una imagen base de Node.js
FROM node:21-alpine

#Pasar url de cola
ENV QUEUE_URL "https://sqs.us-east-1.amazonaws.com/715211652634/skillfullers"

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar el archivo de tu aplicación y el archivo package.json a la imagen
COPY package.json ./
COPY app.js .

# Instalar las dependencias
RUN npm install

# Comando para iniciar tu aplicación
CMD [ "node", "app.js" ]
```

Con esto ya podemos hacer el build de nuestra app y subirla a un ECR

## Rol para deployment sqs

Debemos crear un rol que asumirá el pod, para esto tenemos la siguiente politica y el comando de eksctl para crear nuestro sa

### Archivo sqs_policy.json

```json
{
  "Version": "2012-10-17",
  "Statement": [
      {
          "Effect": "Allow",
          "Action": [
              "sqs:GetQueueUrl",
              "sqs:ReceiveMessage",
              "sqs:DeleteMessage"
          ],
          "Resource": "arn:aws:sqs:us-east-1:121212:yonier-sqs"
      }
  ]
}

```

### Script para crear politica y rol

```bash
#!/bin/bash

#VARIABLES
export AWS_REGION="us-east-1"
POLICY_NAME="sqs-yonier"
POLICY_ARN=$(aws iam list-policies --output text --query 'Policies[?PolicyName==`'$POLICY_NAME'`].Arn')
ROLE_NAME="eksctl-yonier-role"
ID=$(aws sts get-caller-identity --query "Account" --output text)
CLUSTER_NAME=eks-contenerizacionlab-dev


echo ===============================================
echo Create iam policy sqs-skillfullers
echo ===============================================
# aws iam delete-policy --policy-arn arn:aws:iam::327313795930:policy/sqs-skillfullers
if [ -z "$POLICY_ARN" ]; then
    aws iam create-policy \
    --policy-name $POLICY_NAME \
    --policy-document file://sqs_policy.json \
    --description="Rol for sqs eks" \
    --no-paginate > /dev/null 2>&1
else
    echo "La política sqs-yonier ya existe en IAM."
fi


echo ===============================================
echo Create iam role eksctl-skillfullers-role
echo ===============================================
eksctl create iamserviceaccount \
  --cluster=$CLUSTER_NAME \
  --namespace=yonier-nsa \
  --name=yonier-sa  \
  --role-name $ROLE_NAME \
  --attach-policy-arn=arn:aws:iam::$ID:policy/$POLICY_NAME \
  --override-existing-serviceaccounts \
  --approve

echo ===============================================
echo Add Permissions Boundary to $ROLE_NAME
echo ===============================================
# Verificar si el rol ya existe
EXISTING_ROLE=$(aws iam get-role --role-name $ROLE_NAME --output text --query 'Role.RoleName')

# Si el rol ya existe, agregar el límite de permisos
if [ -n "$EXISTING_ROLE" ]; then
    echo "El rol $ROLE_NAME ya existe. Agregando boundary BoundaryName..."
    aws iam put-role-permissions-boundary --role-name $ROLE_NAME \
        --permissions-boundary=arn:aws:iam::$ID:policy/My_boundary #ESTE PARAMETRO ES OPCIONAL SI TIENE BOUNDARY EN SU INFRA
else
    echo "El rol $ROLE_NAME no existe."
fi
```

## Desplegar app

Creamos un deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: yonier-app-sqs
  name: yonier-sqs-dp
  namespace: yonier
spec:
  replicas: 2
  selector:
    matchLabels:
      app: yonier-app-sqs
  template:
    metadata:
      labels:
        app: yonier-app-sqs
    spec:
      serviceAccount: yonier-sa  # Asignación del Service Account aquí
      containers:
      - image: public.ecr.aws/repo-yonier/eks:app-sqs-yonier
        imagePullPolicy: Always
        name: yonier-sqs
        resources:
          limits:
            cpu: 100m
            memory: 200Mi
          requests:
            cpu: 30m
            memory: 90Mi
```

## Crear ScaleObject

Cuando creas un recurso tipo ScaleObject se va a generar un hpa automáticamente que se encargará de escalar las replicas.

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  labels:
    app.bancolombia.com.co/application-code: sq
    app.bancolombia.com.co/cost-center: cost
    app.bancolombia.com.co/env: pdn
    app.bancolombia.com.co/project: "cpe-contenerizacion"
  name: skillfullers-sqs-hpa #Nombre del recurso ScaledObject
  namespace: skillfullers #Ns donde se va a desplegar el recurso
spec:
  maxReplicaCount: 10 #Cantidad máx a escalar pods
  minReplicaCount: 0 #Cantidad min de pods existentes
  pollingInterval: 30 #Frecuencia para revisar los msj en las colas para determinar si debe escalar o desescalar
  cooldownPeriod: 10  # Este es el tiempo en segundos que KEDA esperará antes de desescalar los pods.

  scaleTargetRef:
    name: skillfullers-sqs-dp #Aqui va el nombre de su deployment
  triggers:
  - metadata:
      awsRegion: us-east-1 #Region de aws
    # activationQueueLength: "30"
      identityOwner: operator #Autenticacion
      queueLength: "5" #Cantidad de mensajes que un pod va a soportar
      queueURL: yonierSqs #Nombre de su cola
    type: aws-sqs-queue
```

## Crear rol para keda

Creamos una politica y un rol para keda, usaremos el sa keda-operator

### Policy keda_policy

```yaml
{
    "Version": "2012-10-17",
    "Statement": [
       {
         "Sid": "SQSGetActions",
         "Effect": "Allow",
         "Action": "sqs:GetQueueAttributes",
         "Resource": "*"
       }
    ]
}
```

## Rol keda

```bash
#!/bin/bash

#VARIABLES
export AWS_REGION="us-east-1"
POLICY_NAME="KedaEksPolicy"
POLICY_ARN=$(aws iam list-policies --output text --query 'Policies[?PolicyName==`'$POLICY_NAME'`].Arn')
ROLE_NAME="KedaEksRole"
ID=$(aws sts get-caller-identity --query "Account" --output text)
CLUSTER_NAME=eks-informacion-qa


echo ===============================================
echo Create iam policy KedaEksPolicy
echo ===============================================
# aws iam delete-policy --policy-arn arn:aws:iam::327313795930:policy/KedaEksPolicy
if [ -z "$POLICY_ARN" ]; then
    aws iam create-policy \
    --policy-name $POLICY_NAME \
    --policy-document file://keda_policy.json \
    --description="Rol for keda eks" \
    --no-paginate > /dev/null 2>&1
else
    echo "La política KedaEksPolicy ya existe en IAM."
fi


echo ===============================================
echo Create iam role KedaEksRole
echo ===============================================
eksctl create iamserviceaccount \
  --cluster=$CLUSTER_NAME \
  --namespace=keda \
  --name=keda-operator  \
  --role-name $ROLE_NAME \
  --attach-policy-arn=arn:aws:iam::$ID:policy/$POLICY_NAME \
  --override-existing-serviceaccounts \
  --approve

echo ===============================================
echo Add Permissions Boundary to $ROLE_NAME
echo ===============================================
# Verificar si el rol ya existe
EXISTING_ROLE=$(aws iam get-role --role-name $ROLE_NAME --output text --query 'Role.RoleName')

# Si el rol ya existe, agregar el límite de permisos
if [ -n "$EXISTING_ROLE" ]; then
    echo "El rol $ROLE_NAME ya existe. Agregando permissions-boundary Lz-Governance-Boundary..."
    aws iam put-role-permissions-boundary --role-name $ROLE_NAME \
        --permissions-boundary=arn:aws:iam::$ID:policy/Lz-Governance-Boundary
else
    echo "El rol $ROLE_NAME no existe."
fi
```

## Envíar mensajes a la cola de sqs

Para simular el envío de mensajes a la cola lo haré a través de aws cli.

```bash
aws sqs send-message --queue-url "https://sqs.us-east-1.amazonaws.com/121212/yonierSqs" --message-body "lab $RANDOM" --no-cli-pager
```

Crearé un ciclo para envíar 400 msj 

```bash
#!/bin/bash
queue_url="https://sqs.us-east-1.amazonaws.com/121212/yonierSqs"

for i in {1..400}
do
    result=$(aws sqs send-message --queue-url $queue_url --message-body "lab $RANDOM $i" --no-cli-pager)
    echo "Resultado para el mensaje $i:"
    echo $result
    echo "-------------"
done

```

