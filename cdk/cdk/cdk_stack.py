import os
import dotenv
from pathlib import Path

from aws_cdk import (
    Stack,
    aws_sqs as SQS,
    aws_s3 as S3,
    aws_dynamodb as DynamoDB,
    aws_ecr_assets as ECRAssets,
    aws_ecs as ECS,
    aws_ec2 as EC2,
    aws_iam as IAM,
    aws_logs as logs,
    aws_lambda as LAMBDA,
)

from aws_cdk import RemovalPolicy, Duration
from constructs import Construct


scraper_path = str(Path(__file__).parent.parent.parent / "scraper")
lambda_path = str(Path(__file__).parent.parent.parent / "lambda")
env_path = Path(__file__).parent / '.env'

class CdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        dotenv.load_dotenv(env_path)


        # ===== DYNAMO DB =====
        
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



        # ===== SQS QUEUES =====

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



        # ===== ECS CLUSTER =====
        
        # Create role for ECS task execution
        execution_role = IAM.Role(
            self,
            "ScraperExecutionRole",
            assumed_by = IAM.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies = [
                IAM.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy"),
                IAM.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly")
            ]
        )
        
        # Create role for ECS container
        task_role = IAM.Role(
            self,
            "ScraperTaskRole",
            assumed_by = IAM.ServicePrincipal("ecs-tasks.amazonaws.com")
        )
        
        # Grant permissions to access DynamoDB table
        self.job_posts_table.grant_read_write_data(task_role)

        # Grant permissions to access SQS queues
        self.deduplicated_posts_queue.grant_send_messages(task_role)
        self.dead_letter_queue.queue.grant_send_messages(task_role)
        #self.deduplicated_posts_queue.grant_consume_messages(task_role)
        #self.dead_letter_queue.queue.grant_consume_messages(task_role)
        
        # Search for the aws account default vpc
        vpc = EC2.Vpc.from_lookup(
            self, 
            "DefaultVPC",
            is_default = True,
        )
        
        # Create ECS Cluster in the vpc
        cluster = ECS.Cluster(
            self,
            "LabelAppCluster",
            cluster_name = "label-app-cluster",
            vpc = vpc
        )
        
        # Add EC2 Capacity to the cluster
        cluster.add_capacity(
            "ScraperCapacity",
            instance_type = EC2.InstanceType.of(
                EC2.InstanceClass.T3,    
                EC2.InstanceSize.SMALL   
            ),
            allow_all_outbound = True,
            min_capacity = 0,     # Minimum number of EC2 instances
            max_capacity = 2,     # Maximum number of EC2 instances
            #desired_capacity = 0  # How many instances to start with
        )
        
        # Create Task Definition
        task_definition = ECS.Ec2TaskDefinition(
            self,
            "ScraperTaskDefinition",
            family = "scraper-task",
            execution_role = execution_role,  
            task_role = task_role
        )
        
        # Create the scraper docker image
        self.scraper_image = ECRAssets.DockerImageAsset(
            self,
            "ScraperImage",
            directory = scraper_path,
            asset_name = "Scraper-Image"
        )
        
        # Add container to the task definition
        task_definition.add_container(
            "ScraperContainer",
            image = ECS.ContainerImage.from_docker_image_asset(self.scraper_image),
            #image = ECS.ContainerImage.from_registry("182717586751.dkr.ecr.eu-north-1.amazonaws.com/cdk-hnb659fds-container-assets-182717586751-eu-north-1:699024ec6ffa942f5262b08858e4259e340384ef19cb9538cfc12932a553b23c"),  # Use the image from ECR
            memory_reservation_mib = 1024,  
            cpu = 1024,                      
            logging = ECS.LogDrivers.aws_logs(
                stream_prefix = "scraper-logs",
                log_retention = logs.RetentionDays.ONE_WEEK,
                mode = ECS.AwsLogDriverMode.NON_BLOCKING
            ),
            environment = {
                "AWS_DEFAULT_REGION": self.region,
                "DYNAMODB_TABLE_NAME": self.job_posts_table.table_name,
                "DEDUPLICATED_JOBS_QUEUE_NAME": self.deduplicated_posts_queue.queue_name,
                "DEAD_LETTER_QUEUE_NAME": self.dead_letter_queue.queue.queue_name,
                "SINGLE_JOB_BASE_LINK": "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/"
            }
        )

        # Create ECS Service 
        service = ECS.Ec2Service(
            self,
            "LabelAppService",
            cluster = cluster,
            task_definition = task_definition,
            desired_count = 0,  # How many containers to run
            service_name = "my-scraper-service"
        )


        # ===== LAMBDA FUNCTIONS =====

        # Create lambda function to receive messages from the deduplicated queue
        preprocessing_lambda = LAMBDA.Function(
            self,
            "PreprocessingJobPosts",
            runtime = LAMBDA.Runtime.PYTHON_3_12,
            code = LAMBDA.Code.from_asset(lambda_path),
            handler = "preprocessing.lambda_handler",
            dead_letter_queue = self.dead_letter_queue.queue,
            function_name = "PreprocessingJobPosts",
            environment = {
                "DEDUPLICATED_JOBS_QUEUE_NAME": os.getenv("DEDUPLICATED_POSTS_QUEUE_NAME"),
                #"SNS_TOPIC_ARN": os.getenv("SNS_TOPIC_ARN")
            }
        )