from aws_cdk import (
    Stack,
    aws_sqs as SQS,
    aws_s3 as S3,
    aws_dynamodb as DynamoDB,
)

from aws_cdk import RemovalPolicy
from constructs import Construct

class CdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.job_posts_table = DynamoDB.TableV2(
            self,
            "JobPostsTable",
            table_name = "job_posts_deduplication", 
            partition_key = DynamoDB.Attribute(name="job_id", type=DynamoDB.AttributeType.STRING),
            billing = DynamoDB.Billing.on_demand(),
            point_in_time_recovery_specification = True,
            removal_policy = RemovalPolicy.DESTROY,
            time_to_live_attribute = "ttl"
        )