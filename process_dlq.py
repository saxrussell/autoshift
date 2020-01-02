#!/usr/bin/env python

import boto3
from botocore.exceptions import ClientError


def process_dlq_messages(main_queue_name, dlq_queue_name):
    client = boto3.client('sqs')
    dlq_queue_url = client.get_queue_url(QueueName=dlq_queue_name)['QueueUrl']
    main_queue_url = client.get_queue_url(QueueName=main_queue_name)["QueueUrl"]

    try:
        dlq_msg = client.receive_message(
            QueueUrl=dlq_queue_url,
            MaxNumberOfMessages=1,
            VisibilityTimeout=30,
            WaitTimeSeconds=2
        )
        msg_id = dlq_msg["Messages"][0]["MessageId"]
        msg_body = dlq_msg["Messages"][0]["Body"]
        msg_receipt_handle = dlq_msg["Messages"][0]["ReceiptHandle"]
        print("Received DLQ message id {}".format(msg_id))
    except ClientError as e:
        raise Exception("Error receiving DLQ message: {}".format(e))

    try:
        client.send_message(QueueUrl=main_queue_url, MessageBody=msg_body)
        print("Message id {} has been reinserted into main queue at URL {}".format(msg_id, main_queue_url))
    except ClientError as e:
        raise Exception("Error sending message id {} back to main queue: {}.".format(msg_id, e))

    try:
        print("Deleting DLQ receipt handle {} for message id {}".format(msg_receipt_handle, msg_id))
        client.delete_message(QueueUrl=dlq_queue_url, ReceiptHandle=msg_receipt_handle)
    except ClientError as e:
        raise Exception("Error deleting DLQ message {} after processing with receipt {}. Error: {}".format(
            msg_id,
            msg_receipt_handle,
            e))


if __name__ == '__main__':
    process_dlq_messages("shift_code_redeem", "shift_code_redeem_dlq")
