#!/usr/bin/env python3
import os
import dotenv
from pathlib import Path
import aws_cdk as cdk

from cdk.cdk_stack import CdkStack

env_path = Path(__file__).parent / "cdk" / ".env"
print(f"Loading .env from: {env_path}")

if env_path.exists():
    result = dotenv.load_dotenv(env_path)
    print(f"dotenv.load_dotenv() result: {result}")
else:
    print("Warning: .env file not found!")

config = {
    "dynamodb_table_name": os.getenv("DYNAMODB_TABLE_NAME"),
    "deduplicated_posts_queue_name": os.getenv("DEDUPLICATED_POSTS_QUEUE_NAME"),
    "preprocessed_posts_queue_name": os.getenv("PREPROCESSED_POSTS_QUEUE_NAME"),
    "dead_letter_queue_name": os.getenv("DEAD_LETTER_QUEUE_NAME"),
    "sns_topic_name": os.getenv("SNS_TOPIC_NAME"),
    "s3_bucket_name": os.getenv("S3_BUCKET_NAME"),
    "website_bucket_name": os.getenv("WEBSITE_BUCKET_NAME"),
    "website_url": os.getenv("WEBSITE_URL"),
    "api_gateway_api_id": os.getenv("API_GATEWAY_API_ID"),
    "aws_region": os.getenv("AWS_REGION"),
}


app = cdk.App()
CdkStack(app, "CdkStack",
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    env = cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    #env = cdk.Environment(account='182717586751', region='eu-north-1'),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

app.synth()
