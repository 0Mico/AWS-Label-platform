import os
import awsutils as aws_ut


def lambda_handler(event, context):
    sns_topic_arn = os.getenv('SNS_TOPIC_ARN')
    sqs_queue_url = aws_ut._retrieveSQSQueueUrl(os.getenv("DEDUPLICATED_JOBS_QUEUE_NAME"))
    
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
            
            aws_ut._writeJobToSNSTopic(sns_topic_arn, job)
            
            print(f"Processing job: {job}, receipt handle: {receipt_handle}")
            aws_ut._deleteJobFromSQSQueue(sqs_queue_url, receipt_handle)
            print("Message processed and deleted from the queue")

    except Exception as e:
        print(f"Error processing messages from SQS: {e}")
        return