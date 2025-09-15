import os
import json
import awsutils as aws_ut
from datetime import datetime

def lambda_handler(event, context):
    s3_bucket_name = os.getenv('S3_BUCKET_NAME')
    
    if not s3_bucket_name:
        print("Bucket name not defined")
        return
    
    try:
        for record in event['Records']:
            sns_message = record["Sns"]["Message"]
            json_message = json.loads(sns_message)            
            job_title = json_message.get("Title")
            timestamp = datetime.now().strftime('%Y-%m-%d-%H:%M:%S')

            filename = f"{job_title}-{timestamp}"

            s3_key = f"Preprocessed-posts/{filename}.json"

            aws_ut._saveJobToS3Bucket(s3_bucket_name, sns_message, s3_key)

        return

    
    except Exception as e:
        print(f"Error processing SNS message: {e}")
        return None