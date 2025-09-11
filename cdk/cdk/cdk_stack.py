import os
import dotenv
from pathlib import Path

from aws_cdk import (
    Stack,
    aws_sqs as SQS,
    aws_s3 as S3,
    aws_dynamodb as DynamoDB,
    aws_ecr as ECR,
    aws_ecr_assets as ECRAssets,
    aws_ecs as ECS,
    aws_ec2 as EC2,
)

from aws_cdk import RemovalPolicy, Duration
from constructs import Construct


scraper_path = str(Path(__file__).parent.parent.parent / "scraper")


class CdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create the scraper docker image
        self.scraper_image = ECRAssets.DockerImageAsset(
            self,
            "ScraperImage",
            directory = scraper_path,
            asset_name = "Scraper-Image"
        )
        

        # Create deduplication table
        self.job_posts_table = DynamoDB.TableV2(
            self,
            "JobPostsTable",
            table_name = os.getenv("DYNAMODB_TABLE_NAME"), 
            partition_key = DynamoDB.Attribute(name="Job_ID", type=DynamoDB.AttributeType.STRING),
            billing = DynamoDB.Billing.on_demand(),
            point_in_time_recovery_specification = {
                "point_in_time_recovery_enabled": True
            },
            removal_policy = RemovalPolicy.DESTROY,
            time_to_live_attribute = "ttl"
        )

        # Create dead letter queue
        self.dead_letter_queue = SQS.DeadLetterQueue(
            max_receive_count = 5,
            queue = SQS.Queue(
                self,
                "DeadLetterQueue",
                queue_name = os.getenv("DEAD_LETTER_QUEUE_NAME"),
                visibility_timeout = Duration.seconds(180),
                retention_period = Duration.days(14)
            )
        )

        # Create job posts queue
        self.deduplicated_posts_queue = SQS.Queue(
            self,
            "DeduplicatedJobPostsQueue",
            queue_name = os.getenv("DEDUPLICATED_POSTS_QUEUE_NAME"),
            visibility_timeout = Duration.seconds(180),
            retention_period = Duration.days(14),
            dead_letter_queue = self.dead_letter_queue
        )






        # 2. Search for the aws account default vpc
        vpc = EC2.Vpc.from_lookup(
            self, 
            "DefaultVPC",
            is_default = True,
        )
        
        # 3. Create ECS Cluster (logical grouping)
        cluster = ECS.Cluster(
            self,
            "LabelAppCluster",
            cluster_name = "label-app-cluster",
            vpc = vpc
        )
        
        # 4. Add EC2 Capacity to the cluster
        cluster.add_capacity(
            "ScraperCapacity",
            instance_type = EC2.InstanceType.of(
                EC2.InstanceClass.T3,    # Instance family (t3 = burstable performance)
                EC2.InstanceSize.SMALL   # Instance size (micro = smallest)
            ),
            allow_all_outbound = True,
            min_capacity = 0,     # Minimum number of EC2 instances
            max_capacity = 2,     # Maximum number of EC2 instances
            desired_capacity = 0  # How many instances to start with
        )
        
        # 5. Create Task Definition (the "recipe" for your container)
        task_definition = ECS.Ec2TaskDefinition(
            self,
            "ScraperTaskDefinition",
            family = "scraper-task"  # Name for this task definition family
        )
        
        # 6. Add your container to the task definition
        container = task_definition.add_container(
            "ScraperContainer",
            image = ECS.ContainerImage.from_docker_image_asset(self.scraper_image),
            memory_reservation_mib = 1024,  # Reserve 1024 MB RAM
            cpu = 1024,                      # Reserve 1024 CPU units
        )

        # 8. Create ECS Service (ensures containers keep running)
        service = ECS.Ec2Service(
            self,
            "LabelAppService",
            cluster = cluster,
            task_definition = task_definition,
            desired_count = 0,  # How many containers to run
            service_name = "my-scraper-service"
        )

