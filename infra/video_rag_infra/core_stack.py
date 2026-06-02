"""Core infrastructure for the multimodal video RAG platform.

Defines the async-ingestion backbone: an S3 artifacts bucket, an SQS job
queue with a dead-letter queue, DynamoDB tables for video metadata and job
status, CloudWatch log groups, and scoped IAM roles for the worker and API.
"""

import os
from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_apigatewayv2 as apigwv2,
)
from aws_cdk import (
    aws_apigatewayv2_integrations as apigw_integrations,
)
from aws_cdk import (
    aws_cloudwatch as cloudwatch,
)
from aws_cdk import (
    aws_dynamodb as ddb,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_ecs as ecs,
)
from aws_cdk import (
    aws_events as events,
)
from aws_cdk import (
    aws_events_targets as events_targets,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from aws_cdk import (
    aws_sqs as sqs,
)
from constructs import Construct


def _cors_origins() -> list[str]:
    configured = os.environ.get(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


class CoreStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        repo_root = Path(__file__).resolve().parents[2]
        runtime_secret_name = os.environ.get("VIDEO_RAG_RUNTIME_SECRET_NAME", "video-rag/runtime")
        cors_allow_origins = _cors_origins()

        # S3 bucket for artifacts (keyframes, transcripts, metadata).
        # DESTROY + auto-delete keeps teardown clean for a portfolio project.
        artifacts = s3.Bucket(
            self,
            "Artifacts",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # SQS ingestion queue + dead-letter queue. Long visibility timeout
        # because ingestion jobs are long-running; failures redrive to the DLQ.
        dlq = sqs.Queue(self, "IngestDLQ", retention_period=Duration.days(14))
        ingest_queue = sqs.Queue(
            self,
            "IngestQueue",
            visibility_timeout=Duration.minutes(15),
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=dlq),
        )

        # DynamoDB tables, on-demand billing (~$0 idle).
        videos = ddb.Table(
            self,
            "Videos",
            table_name="videos",
            partition_key=ddb.Attribute(name="video_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        jobs = ddb.Table(
            self,
            "Jobs",
            table_name="jobs",
            partition_key=ddb.Attribute(name="job_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        query_cache = ddb.Table(
            self,
            "QueryCache",
            table_name="query_cache",
            partition_key=ddb.Attribute(name="cache_key", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expires_at",
            removal_policy=RemovalPolicy.DESTROY,
        )
        rate_limits = ddb.Table(
            self,
            "RateLimits",
            table_name="rate_limits",
            partition_key=ddb.Attribute(name="window_key", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expires_at",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # CloudWatch log groups (short retention for cost control).
        api_logs = logs.LogGroup(
            self,
            "ApiLogs",
            log_group_name="/video-rag/api",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )
        worker_logs = logs.LogGroup(
            self,
            "WorkerLogs",
            log_group_name="/video-rag/worker",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )
        dispatcher_logs = logs.LogGroup(
            self,
            "DispatcherLogs",
            log_group_name="/video-rag/dispatcher",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        runtime_secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "RuntimeSecret",
            runtime_secret_name,
        )

        runtime_environment = {
            "AWS_REGION": self.region,
            "BEDROCK_LLM_MODEL_ID": os.environ.get(
                "BEDROCK_LLM_MODEL_ID",
                "global.anthropic.claude-haiku-4-5-20251001-v1:0",
            ),
            "BEDROCK_TEXT_EMBED_MODEL_ID": os.environ.get(
                "BEDROCK_TEXT_EMBED_MODEL_ID",
                "amazon.titan-embed-text-v2:0",
            ),
            "BEDROCK_IMAGE_EMBED_MODEL_ID": os.environ.get(
                "BEDROCK_IMAGE_EMBED_MODEL_ID",
                "amazon.titan-embed-image-v1",
            ),
            "EMBED_DIM": os.environ.get("EMBED_DIM", "1024"),
            "PINECONE_TRANSCRIPT_INDEX": os.environ.get(
                "PINECONE_TRANSCRIPT_INDEX",
                "transcript",
            ),
            "PINECONE_VISUAL_INDEX": os.environ.get("PINECONE_VISUAL_INDEX", "visual"),
            "LANGSMITH_TRACING": os.environ.get("LANGSMITH_TRACING", "true"),
            "LANGSMITH_PROJECT": os.environ.get("LANGSMITH_PROJECT", "multimodal-video-rag"),
            "S3_BUCKET": artifacts.bucket_name,
            "SQS_QUEUE_URL": ingest_queue.queue_url,
            "DYNAMODB_VIDEOS_TABLE": videos.table_name,
            "DYNAMODB_JOBS_TABLE": jobs.table_name,
            "DYNAMODB_QUERY_CACHE_TABLE": query_cache.table_name,
            "DYNAMODB_RATE_LIMIT_TABLE": rate_limits.table_name,
            "SECRETS_MANAGER_SECRET_NAME": runtime_secret_name,
            "CORS_ALLOW_ORIGINS": ",".join(cors_allow_origins),
            "SESSION_COOKIE_SECURE": "true",
            "SESSION_COOKIE_SAMESITE": "none",
            "QUERY_CACHE_TTL_SECONDS": os.environ.get("QUERY_CACHE_TTL_SECONDS", "3600"),
            "RATE_LIMIT_WINDOW_SECONDS": os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"),
            "RATE_LIMIT_MAX_REQUESTS": os.environ.get("RATE_LIMIT_MAX_REQUESTS", "20"),
        }
        api_environment = {
            key: value for key, value in runtime_environment.items() if key != "AWS_REGION"
        }

        # IAM role for the ingestion worker (ECS Fargate task role).
        worker_role = iam.Role(
            self,
            "WorkerRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        artifacts.grant_read_write(worker_role)
        videos.grant_read_write_data(worker_role)
        jobs.grant_read_write_data(worker_role)
        query_cache.grant_read_write_data(worker_role)
        rate_limits.grant_read_write_data(worker_role)
        ingest_queue.grant_consume_messages(worker_role)
        runtime_secret.grant_read(worker_role)
        worker_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=["*"],  # TODO: scope to the Titan model ARNs
            )
        )

        # IAM role for the API (Lambda execution role).
        api_role = iam.Role(
            self,
            "ApiRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        videos.grant_read_data(api_role)
        jobs.grant_read_write_data(api_role)
        query_cache.grant_read_write_data(api_role)
        rate_limits.grant_read_write_data(api_role)
        ingest_queue.grant_send_messages(api_role)
        runtime_secret.grant_read(api_role)
        api_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=["*"],  # TODO: scope to the Claude/Titan model ARNs
            )
        )

        api_function = lambda_.DockerImageFunction(
            self,
            "ApiFunction",
            function_name="video-rag-api",
            code=lambda_.DockerImageCode.from_image_asset(
                str(repo_root),
                file="apps/api/Dockerfile",
            ),
            role=api_role,
            timeout=Duration.seconds(60),
            memory_size=1024,
            architecture=lambda_.Architecture.ARM_64,
            environment=api_environment,
            log_group=api_logs,
        )
        api_integration = apigw_integrations.HttpLambdaIntegration(
            "ApiIntegration",
            api_function,
        )
        http_api = apigwv2.HttpApi(
            self,
            "HttpApi",
            api_name="video-rag-api",
            default_integration=api_integration,
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_credentials=True,
                allow_headers=["content-type", "x-request-id"],
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.POST,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_origins=cors_allow_origins,
                max_age=Duration.hours(1),
            ),
        )

        vpc = ec2.Vpc(
            self,
            "WorkerVpc",
            availability_zones=["us-east-1a", "us-east-1b"],
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
        )
        worker_security_group = ec2.SecurityGroup(
            self,
            "WorkerSecurityGroup",
            vpc=vpc,
            allow_all_outbound=True,
        )
        cluster = ecs.Cluster(self, "WorkerCluster", vpc=vpc, cluster_name="video-rag-worker")
        worker_task = ecs.FargateTaskDefinition(
            self,
            "WorkerTask",
            family="video-rag-ingest",
            cpu=2048,
            memory_limit_mib=4096,
            task_role=worker_role,
            ephemeral_storage_gib=50,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.ARM64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
        )
        worker_task.add_container(
            "IngestWorker",
            image=ecs.ContainerImage.from_asset(
                str(repo_root),
                file="workers/ingest/Dockerfile",
            ),
            environment={
                **runtime_environment,
                "INGEST_FRAME_INTERVAL_SECONDS": os.environ.get(
                    "INGEST_FRAME_INTERVAL_SECONDS",
                    "30",
                ),
                "INGEST_MAX_FRAMES": os.environ.get("INGEST_MAX_FRAMES", "20"),
                "WHISPER_MODEL_SIZE": os.environ.get("WHISPER_MODEL_SIZE", "tiny.en"),
                "TRANSCRIPT_CHUNK_SECONDS": os.environ.get("TRANSCRIPT_CHUNK_SECONDS", "30"),
                "TRANSCRIPT_CHUNK_OVERLAP_SECONDS": os.environ.get(
                    "TRANSCRIPT_CHUNK_OVERLAP_SECONDS",
                    "6",
                ),
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="ingest",
                log_group=worker_logs,
            ),
        )

        dispatcher = lambda_.Function(
            self,
            "WorkerDispatcher",
            function_name="video-rag-worker-dispatcher",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            timeout=Duration.seconds(30),
            memory_size=256,
            log_group=dispatcher_logs,
            code=lambda_.Code.from_inline(
                """
import os
import boto3

ecs = boto3.client("ecs")
sqs = boto3.client("sqs")

def handler(event, context):
    attrs = sqs.get_queue_attributes(
        QueueUrl=os.environ["QUEUE_URL"],
        AttributeNames=["ApproximateNumberOfMessages"],
    )["Attributes"]
    visible = int(attrs.get("ApproximateNumberOfMessages", "0"))
    if visible <= 0:
        return {"started": False, "reason": "empty_queue"}

    running = ecs.list_tasks(
        cluster=os.environ["CLUSTER_ARN"],
        family=os.environ["TASK_FAMILY"],
        desiredStatus="RUNNING",
    ).get("taskArns", [])
    if running:
        return {"started": False, "reason": "worker_already_running", "visible": visible}

    response = ecs.run_task(
        cluster=os.environ["CLUSTER_ARN"],
        taskDefinition=os.environ["TASK_DEFINITION_ARN"],
        launchType="FARGATE",
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": os.environ["SUBNET_IDS"].split(","),
                "securityGroups": os.environ["SECURITY_GROUP_IDS"].split(","),
                "assignPublicIp": "ENABLED",
            }
        },
    )
    return {"started": bool(response.get("tasks")), "visible": visible}
"""
            ),
            environment={
                "QUEUE_URL": ingest_queue.queue_url,
                "CLUSTER_ARN": cluster.cluster_arn,
                "TASK_FAMILY": worker_task.family,
                "TASK_DEFINITION_ARN": worker_task.task_definition_arn,
                "SUBNET_IDS": ",".join([subnet.subnet_id for subnet in vpc.public_subnets]),
                "SECURITY_GROUP_IDS": worker_security_group.security_group_id,
            },
        )
        ingest_queue.grant(dispatcher, "sqs:GetQueueAttributes")
        dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ecs:ListTasks", "ecs:RunTask"],
                resources=["*"],
            )
        )
        dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[
                    worker_task.task_role.role_arn,
                    worker_task.execution_role.role_arn,
                ],
            )
        )
        events.Rule(
            self,
            "WorkerDispatcherSchedule",
            schedule=events.Schedule.rate(Duration.minutes(1)),
            targets=[events_targets.LambdaFunction(dispatcher)],
        )

        dashboard = cloudwatch.Dashboard(
            self,
            "Dashboard",
            dashboard_name="video-rag-phase6",
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="API requests and errors",
                left=[api_function.metric_invocations()],
                right=[api_function.metric_errors()],
            ),
            cloudwatch.GraphWidget(
                title="Ingestion queue depth",
                left=[
                    ingest_queue.metric_approximate_number_of_messages_visible(),
                    dlq.metric_approximate_number_of_messages_visible(),
                ],
            ),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Worker dispatcher",
                left=[dispatcher.metric_invocations()],
                right=[dispatcher.metric_errors()],
            ),
            cloudwatch.GraphWidget(
                title="API latency",
                left=[api_function.metric_duration()],
            ),
        )
        cloudwatch.Alarm(
            self,
            "IngestDlqAlarm",
            metric=dlq.metric_approximate_number_of_messages_visible(),
            threshold=1,
            evaluation_periods=1,
            alarm_description="Ingestion messages have reached the DLQ.",
        )
        cloudwatch.Alarm(
            self,
            "ApiErrorAlarm",
            metric=api_function.metric_errors(period=Duration.minutes(5)),
            threshold=1,
            evaluation_periods=1,
            alarm_description="The deployed API Lambda returned errors.",
        )

        api_logs.add_metric_filter(
            "ApiRequestMetricFilter",
            filter_pattern=logs.FilterPattern.literal("api_request"),
            metric_namespace="VideoRag",
            metric_name="ApiRequestLogLines",
            metric_value="1",
        )

        # Outputs — copy the bucket name and queue URL into .env.
        CfnOutput(self, "ArtifactsBucketName", value=artifacts.bucket_name)
        CfnOutput(self, "IngestQueueUrl", value=ingest_queue.queue_url)
        CfnOutput(self, "IngestDlqUrl", value=dlq.queue_url)
        CfnOutput(self, "VideosTableName", value=videos.table_name)
        CfnOutput(self, "JobsTableName", value=jobs.table_name)
        CfnOutput(self, "QueryCacheTableName", value=query_cache.table_name)
        CfnOutput(self, "RateLimitsTableName", value=rate_limits.table_name)
        CfnOutput(self, "WorkerRoleArn", value=worker_role.role_arn)
        CfnOutput(self, "ApiRoleArn", value=api_role.role_arn)
        CfnOutput(self, "ApiUrl", value=http_api.url or "")
        CfnOutput(self, "WorkerClusterName", value=cluster.cluster_name)
        CfnOutput(self, "WorkerTaskDefinitionArn", value=worker_task.task_definition_arn)
        CfnOutput(self, "RuntimeSecretName", value=runtime_secret_name)
