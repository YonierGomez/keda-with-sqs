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
