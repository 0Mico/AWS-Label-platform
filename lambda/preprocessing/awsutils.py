import os
import boto3
import hashlib
import json


try:
    print("Initializing AWS services...")
    dynamodb = boto3.resource('dynamodb')
    sqs_client = boto3.client('sqs')
    sns_client = boto3.client('sns')
    s3_client = boto3.client('s3')
    
    session = boto3.Session()
    print(f"AWS session region: {session.region_name}")
    print("AWS services initialized successfully")
    
except Exception as e:
    print(f"ERROR: Failed to initialize AWS services: {e}")
    raise


# Retrieve the SQS queue by queue name
def _retrieveSQSQueueUrl(queue_name: str, sqs_client=sqs_client):
    try:
        queue = sqs_client.get_queue_url(QueueName=queue_name)
        return queue.get('QueueUrl')
    
    except Exception as e:
        print(f"Error retrieving SQS queue URL: {e}")
        return None


# Receive 5 messages from the specified queue
def _readJobFromSQSQueue(queue_url: str, sqs_client=sqs_client):
    try:
        response = sqs_client.receive_message(
            QueueUrl = queue_url,
            MaxNumberOfMessages = 5,
        )
        return response.get('Messages', [])
    
    except Exception as e:
        print(f"Error reading message from SQS: {e}")
        return None


# Delete a message from the specified queue
def _deleteJobFromSQSQueue(queue_url: str, receipt_handle: str, sqs_client=sqs_client):
    try:
        sqs_client.delete_message(
            QueueUrl = queue_url,
            ReceiptHandle = receipt_handle
        )
        return
    
    except Exception as e:
        print(f"Error deleting message from SQS: {e}")
        return None


# Publish a job post to the specified sns topic
def _writeJobToSNSTopic(sns_topic_arn: str, job: str, sns_client=sns_client):
    try:
        response = sns_client.publish(
            TopicArn = sns_topic_arn,
            Message = job
        )
        return
    
    except Exception as e:
        print(f"Error publishing message to SNS: {e}")
        return None
    

# Save a job post to the specified S3 bucket
def _saveJobToS3Bucket(bucket_name: str, job: str, key: str, s3_client=s3_client):
    try:
        s3_client.put_object(
            Bucket = bucket_name,
            Key = key,
            Body = job,
            ContentType = "application/json"
        )
        return
    
    except Exception as e:
        print(f"Error saving job to S3: {e}")
        return None