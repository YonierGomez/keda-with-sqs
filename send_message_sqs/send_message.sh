#!/bin/bash
queue_url="https://sqs.us-east-1.amazonaws.com/715211652634/skillfullers"

for i in {1..400}
do
    result=$(aws sqs send-message --queue-url $queue_url --message-body "lab $RANDOM $i" --no-cli-pager)
    echo "Resultado para el mensaje $i:"
    echo $result
    echo "-------------"
done
