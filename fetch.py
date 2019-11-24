#!/usr/bin/env python

from twarc import Twarc
import os
import json
import re
import calendar
import boto3
from botocore.exceptions import ClientError
from datetime import *
from dateutil.parser import *
from pynamodb.models import Model
from pynamodb.attributes import *
from pynamodb.exceptions import DoesNotExist


def get_tweets(tcconfig, up_to_pages=1, source_id="dgSHiftCodes"):
    if tcconfig is not None:
        ct = tcconfig["consumer_key"]
        cs = tcconfig["consumer_secret"]
        at = tcconfig["access_token"]
        ats = tcconfig["access_token_secret"]
    else:
        raise Exception("Twitter client config cannot be None")

    twsclient = Twarc(ct, cs, at, ats)

    return twsclient.timeline(screen_name=source_id, max_pages=up_to_pages)


def get_tweets_with_codes(tweets):
    relevant_tweets = []
    for t in tweets:
        msg = t["full_text"]
        created_at = t["created_at"]
        msg_id = t["id_str"]

        shift_code_search = re.search(r'SHIFT CODE', msg, re.M)

        if shift_code_search is None:
            continue

        bl3_search = re.search(r'BORDERLANDS 3', msg, re.M)

        if bl3_search is None:
            continue
        else:
            relevant_tweets.append({
                "tweet_created": str(parse(created_at)),
                "tweet_id": msg_id,
                "msg": msg
            })
    return relevant_tweets


def add_shift_code(tweets):
    shift_code_added = []
    for t in tweets:
        shift_code = re.search(r'[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}', t["msg"], re.M)

        if shift_code is None:
            continue
        else:
            t["code"] = shift_code.group(0)
            shift_code_added.append(t)
    return shift_code_added


def map_expirations(filtered_tweets):
    tweets = []
    for t in filtered_tweets:
        starttime = parse(t["tweet_created"])
        expires_count = re.search(r'[~]?[0-9]+[.]?[0-9]? (days|hours)', t["msg"], re.M | re.I)

        if expires_count is None:
            t["expire_time"] = expires_count
            tweets.append(t)
            continue
        else:
            split_expires = re.split(r'\s+', expires_count.group(0))
            expire_float = re.sub(r'~', '', split_expires[0])
            expire_interval = split_expires[1]

        if expire_interval == "HOURS":
            t["expire_time"] = str(starttime + timedelta(hours=float(expire_float)))
        elif expire_interval == "DAYS" or expire_interval == "Days":
            t["expire_time"] = str(starttime + timedelta(days=float(expire_float)))
        tweets.append(t)
    return tweets


class ShiftCode(Model):
    """
    object model for storing a tweeted SHiFT code in DynamoDB
      shiftCode     : (string), primary key
      tweetTime     : (number), sort key, in form of epoch timestamp
      tweetMsg      : (string), the raw message in the tweet
      expiresTime   : (number) in form of epoch timestamp
      redeemed      : (bool) true if code is already remdeemed, false if not
      redeemRetry   : (number) number of times redemption has been attempted without success
      published     : (bool) true if code has been published to slack/discord
      publishRetry  : (number) counter for how many publish attempts have been made without success
    """
    class Meta:
        region = os.getenv('AWS_REGION')
        table_name = os.getenv('DYNAMODB_TABLE_NAME', 'autoshift')

    shiftCode = UnicodeAttribute(hash_key=True)
    tweetTime = NumberAttribute(range_key=True)
    tweetMsg = UnicodeAttribute(null=True)
    expiresTime = NumberAttribute(null=True)
    redeemed = BooleanAttribute(default=False)
    redeemRetry = NumberAttribute(default=0)
    published = BooleanAttribute(default=False)
    publishRetry = NumberAttribute(default=0)


def write_dynamo_item(tweet_dict):
    tweet_timestamp = calendar.timegm(parse(tweet_dict["tweet_created"]).timetuple())
    if tweet_dict["expire_time"] is None:
        expire_timestamp = None
    else:
        expire_timestamp = calendar.timegm(parse(tweet_dict["expire_time"]).timetuple())

    shift_entry = ShiftCode(
        tweet_dict["code"],
        tweet_timestamp,
        tweetMsg=tweet_dict["msg"],
        expiresTime=expire_timestamp,
        redeemed=tweet_dict["redeemed"],
        redeemRetry=tweet_dict["redemption_retries"],
        published=tweet_dict["published"],
        publishRetry=tweet_dict["publish_retries"]
    )

    shift_entry.save()


def publish_sqs_message(queue_name, msg_json):
    """This function does not validate the json for msg_json."""
    client = boto3.client('sqs')
    queue_url = client.get_queue_url(QueueName=queue_name)
    client.send_message(QueueUrl=queue_url, MessageBody=msg_json)


def handler_fetch(event=None, context=None):
    # setup the SSM param store client
    ssm_client = boto3.client("ssm")
    twitter_api_ssm_path = '/{}/twitter/api'.format(os.getenv('SSM_PARAM_PATH_NAME', 'autoshift'))
    twitter_api_ssm_params = [
        'consumer_key',
        'consumer_secret',
        'access_token',
        'access_token_secret'
    ]

    # init the twarc client config
    client_config = {}

    # fetch twitter api credentials from param store
    for param in twitter_api_ssm_params:
        fq_param = "{0}/{1}".format(twitter_api_ssm_path, param)
        param_response = ssm_client.get_parameter(Name=fq_param, WithDecryption=True)
        client_config[param] = param_response["Parameter"]["Value"]

    # queue logical names provided to queue function
    redeem_queue_name = os.getenv('REDEEM_QUEUE_NAME', 'shift_code_redeem')
    publish_queue_name = os.getenv('PUBLISH_QUEUE_NAME', 'shift_code_publish')

    print("Fetching latest dgSHiFTCodes tweets from Twitter API")
    all_tweets = get_tweets(client_config)

    print("Filtering out messages that do not contain SHiFT codes")
    tweets_with_codes = get_tweets_with_codes(all_tweets)

    if len(tweets_with_codes) == 0:
        exit('No recent SHiFT codes found')

    print("Parse messages for the actual shift code and add it to the dict")
    mapped_shift_codes = add_shift_code(tweets_with_codes)

    print("Search tweets containing codes for expiration dates and add expire dates to dict")
    final_set = map_expirations(mapped_shift_codes)

    print("Filtration complete. Checking if code is in DB.")
    code_messages_checked = 0
    update_counter = 0
    for parsed_tweet in final_set:
        print("Getting item for shift code {}".format(parsed_tweet["code"]))
        try:
            item = ShiftCode.get(parsed_tweet["code"],
                                 calendar.timegm(parse(parsed_tweet["tweet_created"]).timetuple()))

            item_attrs = item.__dict__
            print("Write not required. Key {} exists.".format(item_attrs['attribute_values']['shiftCode']))
            code_messages_checked += 1

        except DoesNotExist:
            parsed_tweet["redeemed"] = False
            parsed_tweet["published"] = False
            parsed_tweet["redemption_retries"] = 0
            parsed_tweet["publish_retries"] = 0
            print("Write required. Attempting to PutItem to dynamo...")
            write_dynamo_item(parsed_tweet)
            print("Write successful.")
            code_messages_checked += 1
            update_counter += 1
            print("Converting parsed tweet to JSON")

            try:
                parsed_tweet_json = json.dumps(parsed_tweet)

                print("Putting message on redeem queue")

                try:
                    publish_sqs_message(redeem_queue_name, parsed_tweet_json)
                except ClientError as redeem_sqs_err:
                    print("Error encountered publishing message to redeem queue")
                    print(redeem_sqs_err)
                print("Putting message on publish queue")

                try:
                    publish_sqs_message(publish_queue_name, parsed_tweet_json)
                except ClientError as publish_sqs_err:
                    print("Error encountered publishing message to publish queue")
                    print(publish_sqs_err)
            except ValueError as err:
                print("Error converting parsed tweet to JSON")
                print("Downstream redeem/publish lambdas will NOT be triggered")
                print(err)

    print("Finished.")
    print("{} records checked.".format(code_messages_checked))
    print("{} records updated.".format(update_counter))

    return True
