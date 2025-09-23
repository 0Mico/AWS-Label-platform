import os
import json
import preprocessing.awsutils as aws_ut
from datetime import datetime

def lambda_handler(event, context):
    s3_bucket_name = os.getenv('S3_BUCKET_NAME')
    cors_headers = {
        'Access-Control-Allow-Origin': 'http://cdkstack-websitebucket75c24d94-ikl37y2rogki.s3-website.eu-north-1.amazonaws.com',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-Amz-Date, Authorization, X-Api-Key, X-Amz-Security-Token',
        'Content-Type': 'application/json'
    }
    
    if not s3_bucket_name:
        print("Bucket name not defined")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': 'S3 bucket name not configured.'})
        }
    
    try:
        labeled_job_post = event["body"]

        json_labeled_job_post = json.loads(labeled_job_post)
        job_title = json_labeled_job_post.get("Title")
        timestamp = datetime.now().strftime('%Y-%m-%d-%H:%M:%S')

        filename = f"{job_title}-{timestamp}"

        s3_key = f"Labeled-data/{filename}.json"

        aws_ut._saveJobToS3Bucket(s3_bucket_name, labeled_job_post, s3_key)

        return {
            'statusCode': 200,
            'headers': cors_headers,
        }

    except Exception as e:
        print(f"Error processing SNS message: {e}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': f'Failed to save labels: {str(e)}'})
        }