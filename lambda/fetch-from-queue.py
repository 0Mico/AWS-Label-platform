import os
import json
import awsutils as aws_ut


def lambda_handler(event, context):
    sqs_queue_url = os.getenv("PREPROCESSED_JOBS_QUEUE_URL")
    
    if not sqs_queue_url:
        print("SQS queue URL not found")
        return
    
    try:
        messages = aws_ut._readJobFromSQSQueue(sqs_queue_url)
        if not messages:
            print("No messages in the queue")
            return
        
        for message in messages:
            receipt_handle = message.get('ReceiptHandle')
            job = message.get('Body')
            if not job or not receipt_handle:
                print("Message body or receipt handle is empty")
                continue

            print(f"Processing message: {job}")

            aws_ut._deleteJobFromSQSQueue(sqs_queue_url, receipt_handle)
            
            print("Message processed and deleted from the queue")

    except Exception as e:
        print(f"Error processing messages from SQS: {e}")
        return