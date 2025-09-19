import os
import json
import awsutils as aws_ut
from transformers import AutoTokenizer


def _tokenizeText(tokenizer: AutoTokenizer, text: str):
    return tokenizer.tokenize(text)
    

def lambda_handler(event, context):
    sns_topic_arn = os.getenv('SNS_TOPIC_ARN')
    sqs_queue_url = aws_ut._retrieveSQSQueueUrl(os.getenv("DEDUPLICATED_JOBS_QUEUE_NAME"))
    tokenizer = AutoTokenizer.from_pretrained("bert-base-multilingual-uncased")

    
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
            
            try:
                job_data = json.loads(job)
                job_description = job_data.get("Description")
                job_tokenized = _tokenizeText(tokenizer, job_description)
                filtered_job = {
                    "Job_ID": job_data.get("Job_ID"),
                    "Title": job_data.get("Title"),
                    "Company": job_data.get("Company_name"),
                    "Description": job_tokenized
                }
                filtered_json_string = json.dumps(filtered_job, ensure_ascii=False)
                
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                continue

            aws_ut._writeJobToSNSTopic(sns_topic_arn, filtered_json_string)
            
            aws_ut._deleteJobFromSQSQueue(sqs_queue_url, receipt_handle)
            
            print("Message processed and deleted from the queue")

    except Exception as e:
        print(f"Error processing messages from SQS: {e}")
        return