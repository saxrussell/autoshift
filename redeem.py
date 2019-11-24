import os
from shift import ShiftClient
from fetch import ShiftCode
import boto3
from botocore.exceptions import ClientError
import json


def handler_redeem(event, context):

    ssm_client = boto3.client("ssm")
    sqs_client = boto3.client("sqs")

    shift_username, shift_password, shift_client = None, None, None

    try:
        shift_username = ssm_client.get_parameter(Name='/{}/shift_login/username'.format(
            os.getenv('SSM_PARAM_PATH_NAME', 'autoshift')))
        shift_password = ssm_client.get_parameter(Name='/{}/shift_login/password'.format(
            os.getenv('SSM_PARAM_PATH_NAME', 'autoshift')),
                                                  WithDecryption=True)
    except ClientError as ssm_error:
        print("FAILURE : Error getting SHiFT login credentials.")
        exit(ssm_error)

    if shift_username is not None and shift_password is not None:
        shift_client = ShiftClient(user=shift_username["Parameter"]["Value"],
                                   pw=shift_password["Parameter"]["Value"])

    for rec in event['Records']:
        msg_body = None
        try:
            msg_body = json.loads(rec['body'])
        except json.JSONDecodeError as e:
            exit(e)

        # only redeem for epic right now.
        platform = 'epic'
        redeemed = shift_client.redeem(msg_body["code"], platform)

        if redeemed:
            # write redeemed state to dynamo
            print("SUCCESS : SHiFT code has been redeemed in shift.gearboxsoftware.com!")
            print("Updating database...")
            try:
                # pull the current db item into memory
                shift_item = ShiftCode.get(msg_body['code'], msg_body['tweet_created'])

                # update the redeemed value on the local memory item
                shift_item.update(
                    actions=[
                        ShiftCode.redeemed.set(True)
                    ]
                )

            except Exception as db_write_err:
                print("FAILURE : Something went wrong with the database update.")
                print(db_write_err)

            # validate the write
            try:
                updated_shift_item = ShiftCode.get(msg_body['code'], msg_body['tweet_created'])
                updated_item_attrs = updated_shift_item.__dict__
                if updated_item_attrs["attribute_values"]["redeemed"]:
                    print("SUCCESS : SHiFT code redeem status updated in database.")
                    print("Deleting message from queue")
                    queue_name = os.getenv('REDEEM_QUEUE_NAME', 'shift_code_redeem')
                    sqs_url = sqs_client.get_queue_url(QueueName=queue_name)
                    sqs_client.delete_message(QueueUrl=sqs_url, ReceiptHandle=rec["receiptHandle"])
                else:
                    print("FAILURE : SHiFT code redeem state for {} not updated correctly.".format(msg_body["code"]))

            except Exception as validation_error:
                print(validation_error)
        else:
            exit("Redeem failed")
