import os
import boto3
import hashlib
import json


try:
    print("Initializing AWS services...")
    dynamodb = boto3.resource('dynamodb')
    sqs_client = boto3.client('sqs')
    sns_client = boto3.client('sns')
    
    session = boto3.Session()
    print(f"AWS session region: {session.region_name}")
    print("AWS services initialized successfully")
    
except Exception as e:
    print(f"ERROR: Failed to initialize AWS services: {e}")
    raise



# Retrieve the DynamoDB table by table name
def _retrieveDynamoDBTable(table_name: str, dynamodb=dynamodb):
    try:
        table = dynamodb.Table(table_name)
        return table
    
    except Exception as e:
        print(f"Error retrieving DynamoDB table: {e}")
        return None


# Save the job object received into the DynamoDB table passed
def _saveJobToDynamoDB(db_table, job: dict):
    try:
        db_table.put_item(Item=job)
        return 
    
    except Exception as e:
        print(f"Error saving job to DynamoDB: {e}")
        return None

    
# Update the job adding the description field
def _updateJobInDynamoDB(db_table, job: dict):
    try:
        db_table.update_item(
            Key = {'Job_ID': job['Job_ID']},
            UpdateExpression = "SET Sent_to_queue = :val",
            ExpressionAttributeValues ={
                ':val': job['Sent_to_queue']
            },
            ReturnValues="UPDATED_NEW"
        )
        return

    except Exception as e:
        print(f"Error updating job in DynamoDB: {e}")
        return None


# Check if the job with the id received already exists in the table passed
def _checkIfJobExists(db_table, job_id: str):
    try:
        response = db_table.get_item(Key={'Job_ID': str(job_id)})
        return response.get('Item')
    
    except Exception as e:
        print(f"Error checking job existence: {e}")
        return None 


# Retrieve the SQS queue by queue name
def _retrieveSQSQueueUrl(queue_name: str, sqs_client=sqs_client):
    try:
        queue = sqs_client.get_queue_url(QueueName=queue_name)
        return queue.get('QueueUrl')
    
    except Exception as e:
        print(f"Error retrieving SQS queue URL: {e}")
        return None


# Write the job in the SQS queue
def _writeJobToSQSQueue(sqs_queue, job: dict, sqs_client=sqs_client):
    try:
        job_string = json.dumps(job, ensure_ascii=False, default=str) # Send message method needs a string
        job_md5 = hashlib.md5(str(job_string).encode()).hexdigest()
        response = sqs_client.send_message(QueueUrl=sqs_queue, MessageBody=job_string)
        if response.get('MD5OfMessageBody') == job_md5:
            print("Hash corresponds")
        else:
            print("Hash does not correspond")

    except Exception as e:
        print(f"Error sending message to SQS: {e}")
        return None
    
    job['Sent_to_queue'] = True
    _updateJobInDynamoDB(_retrieveDynamoDBTable(os.getenv("DYNAMODB_TABLE_NAME")), job)
    return


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