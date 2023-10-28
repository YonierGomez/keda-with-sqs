#!/bin/bash

#VARIABLES
export AWS_REGION="us-east-1"
POLICY_NAME="sqs-skillfullers"
POLICY_ARN=$(aws iam list-policies --output text --query 'Policies[?PolicyName==`'$POLICY_NAME'`].Arn')
ROLE_NAME="eksctl-skillfullers-role"
ID=$(aws sts get-caller-identity --query "Account" --output text)
CLUSTER_NAME=eks-contenerizacionlab-dev


echo ===============================================
echo Create iam policy sqs-skillfullers
echo ===============================================
# aws iam delete-policy --policy-arn arn:aws:iam::327313795930:policy/sqs-skillfullers
if [ -z "$POLICY_ARN" ]; then
    aws iam create-policy \
    --policy-name $POLICY_NAME \
    --policy-document file://sqs.json \
    --description="Rol for sqs eks" \
    --no-paginate > /dev/null 2>&1
else
    echo "La política sqs-skillfullers ya existe en IAM."
fi


echo ===============================================
echo Create iam role eksctl-skillfullers-role
echo ===============================================
eksctl create iamserviceaccount \
  --cluster=$CLUSTER_NAME \
  --namespace=skillfullers \
  --name=skillfullers-sa  \
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