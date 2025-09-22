import os
import json
import preprocessing.awsutils as aws_ut


def lambda_handler(event, context):
    sqs_queue_url = os.getenv("PREPROCESSED_JOBS_QUEUE_URL")
    processed_jobs = []
    cors_headers = {
        'Access-Control-Allow-Origin': 'http://cdkstack-websitebucket75c24d94-ikl37y2rogki.s3-website.eu-north-1.amazonaws.com',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-Amz-Date, Authorization, X-Api-Key, X-Amz-Security-Token',
        'Content-Type': 'application/json'
    }

    if not sqs_queue_url:
        print("SQS queue URL not found")
        return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({
                    'error': 'SQS queue URL not found',
                    'jobs': []
                })
        }
    
    try:
        messages = aws_ut._readJobFromSQSQueue(sqs_queue_url)
        if not messages:
            print("No messages in the queue")
            return {
                    'statusCode': 200,
                    'headers': cors_headers,
                    'body': json.dumps({
                        'message': 'No messages in the queue',
                        'jobs': []
                    })
            }
        
        for message in messages:
            receipt_handle = message.get('ReceiptHandle')
            job = message.get('Body')
            if not job or not receipt_handle:
                print("Message body or receipt handle is empty")
                continue

            try:
                job_data = json.loads(job)
                bert_tokens = job_data.get('Description', [])
                token_objects = []
                if isinstance(bert_tokens, list):
                    for i, token in enumerate(bert_tokens):
                        token_objects.append({
                            'id': i,
                            'text': token,
                            'label': '',
                            'position': i
                        })

                formatted_job = {
                    'Job_ID': job_data.get('Job_ID'),
                    'Title': job_data.get('Title', 'No title'),
                    'Company': job_data.get('Company', 'No company'),
                    'Tokens': token_objects,
                    'Total_tokens': len(token_objects)
                }
                
                processed_jobs.append(formatted_job)

            except Exception as e:
                print(f"Error parsing job body: {e}")

            print(f"Processing message: {job}")

            aws_ut._deleteJobFromSQSQueue(sqs_queue_url, receipt_handle)
            
            print("Message processed and deleted from the queue")
        
        return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({
                    'message': f'Successfully processed {len(processed_jobs)} jobs',
                    'jobs': processed_jobs
                })
        }

    except Exception as e:
        print(f"Error processing messages from SQS: {e}")
        return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({
                    'error': f'Error processing messages from SQS: {str(e)}',
                    'jobs': []
                })
        }
            