import os
import boto3
import hashlib
import json
from dotenv import load_dotenv


load_dotenv()


# Setup AWS credentials: use .env file if running locally. Otherwise, use IAM role credentials (ECS environment)
def _setupAWSSession():
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_DEFAULT_REGION", "eu-north-1")

    if aws_access_key and aws_secret_key:
        # Running locally with explicit credentials from .env
        print("Using explicit AWS credentials from .env file")
        os.environ['AWS_ACCESS_KEY_ID'] = aws_access_key
        os.environ['AWS_SECRET_ACCESS_KEY'] = aws_secret_key
        os.environ['AWS_DEFAULT_REGION'] = aws_region
    else:
        # Running in ECS - use IAM role credentials (automatic)
        print("Using IAM role credentials (ECS environment)")
        # Ensure region is set
        if not os.environ.get('AWS_DEFAULT_REGION'):
            os.environ['AWS_DEFAULT_REGION'] = aws_region


_setupAWSSession()


try:
    print("Initializing AWS services...")
    dynamodb = boto3.resource('dynamodb')
    sqs_client = boto3.client('sqs')
    
    # Test the connection
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