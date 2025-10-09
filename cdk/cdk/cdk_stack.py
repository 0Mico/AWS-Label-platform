from pathlib import Path

from aws_cdk import (
    Stack,
    aws_ecr_assets as ECRAssets,
    aws_dynamodb as DynamoDB,
    aws_lambda as LAMBDA,
    aws_iam as IAM,
    aws_ec2 as EC2,
    aws_ecs as ECS,
    aws_sqs as SQS,
    aws_sns as SNS,
    aws_sns_subscriptions as sns_subscriptions,
    aws_s3 as S3,
    aws_apigateway as APIGateway,
    aws_logs as logs
)

from aws_cdk import RemovalPolicy, Duration
from aws_cdk import aws_s3_deployment as S3Deploy
from constructs import Construct


scraper_path = str(Path(__file__).parent.parent.parent / "scraper")
lambda_path = str(Path(__file__).parent.parent.parent / "lambda")
website_path = str(Path(__file__).parent.parent.parent / "webapp")


class CdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ===== DYNAMO DB =====
        
        # Create deduplication table
        self.job_posts_table = DynamoDB.TableV2(
            self,
            "JobPostsTable",
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
                visibility_timeout = Duration.seconds(180),
                retention_period = Duration.days(14)
            )
        )

        # Create job posts queue for deduplicated posts
        self.deduplicated_posts_queue = SQS.Queue(
            self,
            "DeduplicatedJobPostsQueue",
            visibility_timeout = Duration.seconds(180),
            retention_period = Duration.days(14),
            dead_letter_queue = self.dead_letter_queue
        )

        # Create preprocessed job posts queue
        self.preprocessed_job_posts_queue = SQS.Queue(
            self,
            "PreprocessedJobPostsQueue",
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
            min_capacity = 1,     # Minimum number of EC2 instances
            max_capacity = 2,     # Maximum number of EC2 instances
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



        # ===== SNS TOPIC =====

        # Create SNS topic where lambda function will write to
        self.sns_topic = SNS.Topic(
            self,
            "PreprocessedJobPostsTopic",
        )

        # Subscribe the preprocessed job posts SQS queue to the SNS topic
        self.sns_topic.add_subscription(
            sns_subscriptions.SqsSubscription(
                self.preprocessed_job_posts_queue,
                dead_letter_queue = self.dead_letter_queue.queue,
                raw_message_delivery = True
            )
        )



        # ===== S3 BUCKET =====

        # Create S3 bucket for job posts
        self.s3_bucket = S3.Bucket(
            self,
            "LabelAppBucket",
            removal_policy = RemovalPolicy.DESTROY,
            auto_delete_objects = True,
            block_public_access = S3.BlockPublicAccess.BLOCK_ALL,
        )


        # Create s3 bucket for web page hosting
        self.website_bucket = S3.Bucket(
            self,
            "WebsiteBucket",
            website_index_document = "index.html",
            removal_policy = RemovalPolicy.DESTROY,
            auto_delete_objects = True,
            public_read_access = True,
            block_public_access = S3.BlockPublicAccess(
                block_public_acls = False,
                block_public_policy = False,
                ignore_public_acls = False,
                restrict_public_buckets = False
            )
        )

        # Deploy website files into the bucket. This will ignore the config.js because it is in the gitignore
        website_deployment = S3Deploy.BucketDeployment(
            self,
            "WebsiteDeployment",
            sources = [S3Deploy.Source.asset(website_path)],
            include = [website_path + "/js/config.js"],
            destination_bucket = self.website_bucket
        )



        # ===== LAMBDA FUNCTIONS =====

        # Create docker image for preprocessing lambda function
        preprocessing_image = ECRAssets.DockerImageAsset(
            self,
            "PreprocessingImage",
            directory = lambda_path + "/preprocessing",
            asset_name = "Preprocessing-Lambda-Image"
        )

        # Create preprocessing lambda function from the docker image
        preprocessing_lambda = LAMBDA.Function(
            self,
            "PreprocessingJobPostsImage",
            runtime = LAMBDA.Runtime.FROM_IMAGE,
            code = LAMBDA.Code.from_ecr_image(
                repository = preprocessing_image.repository,
                tag_or_digest = preprocessing_image.asset_hash
            ),
            handler = LAMBDA.Handler.FROM_IMAGE,
            dead_letter_queue = self.dead_letter_queue.queue,
            timeout = Duration.seconds(180),
            memory_size = 1024,
            function_name = "ConteinerizedPreprocessingJobPosts",
            environment = {
                "DEDUPLICATED_JOBS_QUEUE_NAME": self.deduplicated_posts_queue.queue_name,
                "SNS_TOPIC_ARN": self.sns_topic.topic_arn
            }
        )
        self.deduplicated_posts_queue.grant_consume_messages(preprocessing_lambda)
        self.sns_topic.grant_publish(preprocessing_lambda)


        # Create lambda function to save messages from the SNS topic to s3 bucket
        sns_to_s3 = LAMBDA.Function(
            self,
            "SavePreprocessedJobsToS3",
            runtime = LAMBDA.Runtime.PYTHON_3_12,
            code = LAMBDA.Code.from_asset(lambda_path),
            handler = "sns-to-s3.lambda_handler",
            dead_letter_queue = self.dead_letter_queue.queue,
            function_name = "SavePreprocessedJobsToS3",
            environment = {
                "SNS_TOPIC_ARN": self.sns_topic.topic_arn,
                "S3_BUCKET_NAME": self.s3_bucket.bucket_name
            }
        )
        self.s3_bucket.grant_write(sns_to_s3)
        
        # Subscribe the lambda function to the sns topic
        self.sns_topic.add_subscription(
            sns_subscriptions.LambdaSubscription(
                sns_to_s3,
            )
        )


        # Create lambda function to bring preprocessed posts to the web page
        fetch_posts = LAMBDA.Function(
            self,
            "FetchJobsFromQueue",
            runtime = LAMBDA.Runtime.PYTHON_3_12,
            code = LAMBDA.Code.from_asset(lambda_path),
            handler = "fetch-from-queue.lambda_handler",
            dead_letter_queue = self.dead_letter_queue.queue,
            function_name = "FetchJobsFromQueue",
            environment = {
                "PREPROCESSED_JOBS_QUEUE_URL": self.preprocessed_job_posts_queue.queue_url,
                "CORS_ORIGIN": self.website_bucket.bucket_website_url,
            }
        )
        self.preprocessed_job_posts_queue.grant_consume_messages(fetch_posts)


        # Create lambda function to save labeled posts to s3 bucket
        save_labeled_posts = LAMBDA.Function(
            self,
            "SvaePostsToS3",
            runtime = LAMBDA.Runtime.PYTHON_3_12,
            code = LAMBDA.Code.from_asset(lambda_path),
            handler = "save-to-s3.lambda_handler",
            dead_letter_queue = self.dead_letter_queue.queue,
            function_name = "SaveJobsToS3",
            environment = {
                "S3_BUCKET_NAME": self.s3_bucket.bucket_name,
                "CORS_ORIGIN": self.website_bucket.bucket_website_url,
                "LABELED_POSTS_PREFIX" : "labeled_posts/"
            }
        )
        self.s3_bucket.grant_write(save_labeled_posts)



        # ===== API GATEWAY =====

        # Create API gateway to route website requests
        self.api_gateway = APIGateway.RestApi(
            self,
            "LabelAppAPI",
            rest_api_name = "Label-app-API",
            description = "API for the Label App",
            deploy = True,
            deploy_options = APIGateway.StageOptions(
                stage_name = "prod"
            )
        )

        jobs_resource = self.api_gateway.root.add_resource("Job-Posts")
        jobs_resource.add_cors_preflight(
            allow_origins = [self.website_bucket.bucket_website_url],
            allow_methods = ["GET", "POST", "OPTIONS"],
            allow_headers = ["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key", "X-Amz-Security-Token"]
        )
        jobs_resource.add_method(
            "GET",
            APIGateway.LambdaIntegration(fetch_posts),
        )
        jobs_resource.add_method(
            "POST",
            APIGateway.LambdaIntegration(save_labeled_posts),
        )