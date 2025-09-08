import os
import boto3
import hashlib
import json
from dotenv import load_dotenv


dynamodb = boto3.resource('dynamodb')
sqs_client = boto3.client('sqs')


# Setup AWS session with credentials stored in .env file
def _setupAWSSession():
    os.environ['AWS_ACCESS_KEY_ID'] = os.getenv("AWS_ACCESS_KEY_ID")
    os.environ['AWS_SECRET_ACCESS_KEY'] = os.getenv("AWS_SECRET_ACCESS_KEY")
    os.environ['AWS_DEFAULT_REGION'] = os.getenv("AWS_DEFAULT_REGION")
    return


# Retrieve the DynamoDB table by table name
def _retrieveDynamoDBTable(table_name: str, dynamodb=dynamodb):
    try:
        table = dynamodb.Table(table_name)
        return table
    
    except Exception as e:
        print(f"Error retrieving DynamoDB table: {e}")
        return None


# Retrieve the SQS queue by queue name
def _retrieveSQSQueueUrl(queue_name: str, sqs_client=sqs_client):
    try:
        queue = sqs_client.get_queue_url(QueueName=queue_name)
        return queue.get('QueueUrl')
    
    except Exception as e:
        print(f"Error retrieving SQS queue URL: {e}")
        return None
    
    
# Check if the job with the id received already exists in the table passed
def _checkIfJobExists(db_table, job_id: str):
    try:
        response = db_table.get_item(Key={'Job_ID': str(job_id)})
        return response.get('Item')
    
    except Exception as e:
        print(f"Error checking job existence: {e}")
        return None    


# Save the job object received into the DynamoDB table passed
def _saveJobToDynamoDB(db_table, job: dict):
    try:
        db_table.put_item(Item=job)
        return 
    
    except Exception as e:
        print(f"Error saving job to DynamoDB: {e}")

    
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
        return
    
    job['Sent_to_queue'] = True
    _updateJobInDynamoDB(_retrieveDynamoDBTable(os.getenv("DYNAMODB_TABLE_NAME")), job)
    return