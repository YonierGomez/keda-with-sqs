SQS Consumer App escrita en nodejs con la finalidad de leer los mensajes de una cola de sqs y mostrarlos en pantalla.
======================  
## Referencia rápida
* [¿Qué es web sqs?](#qué-es-web-sqs)
* [¿Cuál es nuestro uso?](#cuál-es-nuestro-uso)
* [¿Cómo usar esta imagen?](#cómo-usar-esta-imagen)
* [Arquitectura soportada](#arquitectura-soportada)
* [Variables](#variables)
* [Uso en raspberry](#uso-en-raspberry)
* [Te invito a visitar mi web](#te-invito-a-visitar-mi-web)


## ¿Qué es web sqs?

Amazon Simple Queue Service (Amazon SQS) es un servicio de mensajería completamente administrado que facilita el intercambio de mensajes entre aplicaciones y componentes de software en la nube. Amazon SQS permite la desacoplar y escalar microservicios, sistemas distribuidos y aplicaciones sin servidores.

Los mensajes enviados a través de Amazon SQS se almacenan en una cola hasta que se procesan o se eliminan. Este servicio puede transmitir cualquier volumen de datos, sin perder mensajes ni necesitar otros servicios adicionales. Puede integrarse con otros servicios de AWS para crear soluciones escalables y fiables.

Amazon SQS ofrece dos tipos de colas: colas estándar y colas FIFO (First-In-First-Out). Las colas estándar ofrecen una entrega de mensajes al menos una vez, mientras que las colas FIFO ofrecen una entrega exactamente una vez. Cada tipo de cola tiene sus propias características y casos de uso recomendados.



![sqs](https://d1.awsstatic.com/legal/AmazonMessaging_SQS_SNS/product-page-diagram_Amazon-SQS%402x.6df419be87198e0f8b0c8151eceac65584db78ea.png)

## ¿Cuál es nuestro uso?

Esta app fue construida en nodejs y tiene como finalidad leer los mensajes de una cola de sqs, su rol es de consumidor. 
  

## ¿Cómo usar esta imagen?

Puede hacer uso de docker cli o docker compose

### Requisitos indispensables

Debe pasar la variable `-e QUEUE_URL=URL-COLA-SQS"`
  
### docker-compose (recomendado)

```yaml
---
version: '3'
services:
  sqs_consumer:
    image: neytor/sqs-consumer
    container_name: sqs_consumer_container
    restart: always
    environment:
      - QUEUE_URL=URL-COLA-SQS #OBLIGATORIO

...
```

> Nota: Puedes reemplazar environment por env_file y pasarle un archivo .env como valor, recuerde que el archivo .env debe tener las variables deseadas.

### docker cli

```bash
docker container run \
   --name sqs_consumer -e QUEUE_URL=URL-COLA-SQS
   -d neytor/sqs-consumer
```

## Arquitectura soportada
La arquitectura soportada es la siguiente:

| Arquitectura | Disponible | Tag descarga |
| ------------ | ---------- | ---------------------------- |
| x86-64 | ✅ | docker pull neytor/sqs-consumer |
| arm64 | ✅ | docker pull neytor/sqs-consumer:arm |

## Variables
Puedes pasar las siguientes variables al crear el contenedor

| Variable | Función |
| ------------- | ------------------------------------------------------------ |
| `-e QUEUE_URL` |**Obligatorio:** Es la url de la cola de sqs |


## Environment variables desde archivo (Docker secrets)

Se recomienda pasar la variable `TOKEN`a través de un archivo.

## Uso en Raspberry

Puedes utilizarla para cualquier raspberry pi

```bash
docker container run \
  --name sqs_consumer -e QUEUE_URL=URL-COLA-SQS
  -d neytor/sqs-consumer:arm
```

[![Try in PWD](https://github.com/play-with-docker/stacks/raw/cff22438cb4195ace27f9b15784bbb497047afa7/assets/images/button.png)](http://play-with-docker.com?stack=https://raw.githubusercontent.com/docker-library/docs/db214ae34137ab29c7574f5fbe01bc4eaea6da7e/wordpress/stack.yml)

## Te invito a visitar mi web

Puedes ver nuevos eventos en [https://www.yonier.com/](https://www.yonier.com)
