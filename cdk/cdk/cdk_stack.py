from aws_cdk import (
    Stack,
    aws_sqs as SQS,
    aws_s3 as S3,
    aws_dynamodb as DynamoDB,
    aws_ecr as ECR,
)

from aws_cdk import RemovalPolicy, Duration
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
            point_in_time_recovery_specification = {
                "point_in_time_recovery_enabled": True
            },
            removal_policy = RemovalPolicy.DESTROY,
            time_to_live_attribute = "ttl"
        )

        self.dead_letter_queue = SQS.DeadLetterQueue(
            max_receive_count = 5,
            queue = SQS.Queue(
                self,
                "DeadLetterQueue",
                queue_name = "dead_letter_queue",
                visibility_timeout = Duration.seconds(180),
                retention_period = Duration.days(14)
            )
        )

        self.deduplicated_posts_queue = SQS.Queue(
            self,
            "DeduplicatedJobPostsQueue",
            queue_name = "deduplicated_job_posts_queue",
            visibility_timeout = Duration.seconds(180),
            retention_period = Duration.days(14),
            dead_letter_queue = self.dead_letter_queue
        )