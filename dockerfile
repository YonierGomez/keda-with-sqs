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
