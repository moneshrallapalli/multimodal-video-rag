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
        ("http://localhost:3000,http://127.0.0.1:3000,https://multimodal-video-rag-web.vercel.app"),
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
        # Listing jobs by creation order requires a GSI; raw scans return scan
        # order and silently shadow newer jobs past Limit. All items share a
        # constant partition value ("all") since the demo never exceeds a few
        # hundred jobs — a single hot partition is fine for that scale, and the
        # sort key gives us proper descending pagination by created_at.
        jobs.add_global_secondary_index(
            index_name="JobsByCreatedAt",
            partition_key=ddb.Attribute(name="gsi_partition", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="created_at", type=ddb.AttributeType.STRING),
            projection_type=ddb.ProjectionType.ALL,
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
        reranker_logs = logs.LogGroup(
            self,
            "RerankerLogs",
            log_group_name="/video-rag/reranker",
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
            "ENABLE_HYBRID_TRANSCRIPT": os.environ.get("ENABLE_HYBRID_TRANSCRIPT", "true"),
            # Cross-encoder reranking requires loading BAAI/bge-reranker-base (~500 MB)
            # on first invocation.  API Gateway HTTP has a hard 30-second integration
            # timeout that cannot be extended, so cold-start model loading always
            # causes a 503.  Keep this off in the deployed API; the eval harness loads
            # the model locally and reports the real improvement (MRR +1.4 pp).
            "ENABLE_CROSS_ENCODER_RERANK": os.environ.get("ENABLE_CROSS_ENCODER_RERANK", "false"),
            "ENABLE_QUERY_REWRITE": os.environ.get("ENABLE_QUERY_REWRITE", "true"),
            "HYBRID_ALPHA": os.environ.get("HYBRID_ALPHA", "0.7"),
            "SEARCH_CONFIG_VERSION": os.environ.get(
                "SEARCH_CONFIG_VERSION",
                "hybrid-rerank-rewrite-v2",
            ),
            "SESSION_COOKIE_SECURE": "true",
            # Production browser path is Vercel → Next rewrites → API Gateway, which
            # the browser sees as same-origin. `lax` is sufficient there and avoids
            # the CSRF surface that `none` opens. (Direct browser → API Gateway from
            # a different origin is not supported by design.)
            "SESSION_COOKIE_SAMESITE": "lax",
            "QUERY_CACHE_TTL_SECONDS": os.environ.get("QUERY_CACHE_TTL_SECONDS", "3600"),
            "RATE_LIMIT_WINDOW_SECONDS": os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"),
            "RATE_LIMIT_MAX_REQUESTS": os.environ.get("RATE_LIMIT_MAX_REQUESTS", "20"),
        }
        api_environment = {
            key: value for key, value in runtime_environment.items() if key != "AWS_REGION"
        }

        # Bedrock model ARNs for least-privilege IAM. Claude Haiku 4.5 uses a
        # cross-region inference profile (global.*) that lives in the caller's
        # account; invoke also requires permission on the underlying foundation
        # models the profile fans out to (anthropic.claude-haiku-4-5*).
        llm_model_id = runtime_environment["BEDROCK_LLM_MODEL_ID"]
        text_embed_model_id = runtime_environment["BEDROCK_TEXT_EMBED_MODEL_ID"]
        image_embed_model_id = runtime_environment["BEDROCK_IMAGE_EMBED_MODEL_ID"]

        def _foundation_model_arn(model_id: str) -> str:
            # Foundation-model ARNs are region-scoped with no account segment.
            return f"arn:aws:bedrock:{self.region}::foundation-model/{model_id}"

        llm_inference_profile_arn = (
            f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/{llm_model_id}"
        )
        # The Haiku 4.5 global inference profile fans out to per-region foundation
        # models; allow the underlying Anthropic Haiku 4.5 model family.
        llm_underlying_model_arn = (
            "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-*"
        )
        text_embed_arn = _foundation_model_arn(text_embed_model_id)
        image_embed_arn = _foundation_model_arn(image_embed_model_id)

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
        # Worker needs Titan embeddings for indexing and Claude Haiku for frame captioning.
        worker_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    llm_inference_profile_arn,
                    llm_underlying_model_arn,
                    text_embed_arn,
                    image_embed_arn,
                ],
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
        artifacts.grant_read(api_role)
        jobs.grant_read_write_data(api_role)
        query_cache.grant_read_write_data(api_role)
        rate_limits.grant_read_write_data(api_role)
        ingest_queue.grant_send_messages(api_role)
        runtime_secret.grant_read(api_role)
        # API invokes the Claude Haiku 4.5 cross-region inference profile (which
        # requires the profile ARN AND the underlying foundation models it routes
        # to) plus Titan text + image embeddings for retrieval.
        api_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    llm_inference_profile_arn,
                    llm_underlying_model_arn,
                    text_embed_arn,
                    image_embed_arn,
                ],
            )
        )

        reranker_function = lambda_.DockerImageFunction(
            self,
            "RerankerFunction",
            function_name="video-rag-reranker",
            code=lambda_.DockerImageCode.from_image_asset(
                str(repo_root),
                file="apps/api/Dockerfile",
                cmd=["api.rerank_handler.handler"],
            ),
            timeout=Duration.seconds(30),
            memory_size=int(os.environ.get("RERANKER_MEMORY_SIZE", "2048")),
            architecture=lambda_.Architecture.ARM_64,
            log_group=reranker_logs,
        )
        reranker_provisioned_concurrency = int(
            os.environ.get("RERANKER_PROVISIONED_CONCURRENCY", "0")
        )
        if reranker_provisioned_concurrency > 0:
            reranker_invoke_target = lambda_.Alias(
                self,
                "RerankerLiveAlias",
                alias_name="live",
                version=reranker_function.current_version,
                provisioned_concurrent_executions=reranker_provisioned_concurrency,
            )
        else:
            reranker_invoke_target = reranker_function
        reranker_invoke_target.grant_invoke(api_role)
        # Only route to the reranker Lambda when provisioned concurrency is on
        # (i.e. it is warm). With provisioned_concurrency=0 the first invocation
        # would cold-start and exceed its own timeout.  When the function name is
        # absent the API falls back to loading the model locally (baked into the
        # API container image), which is slower on the first cold-start but
        # reliable thereafter.
        if reranker_provisioned_concurrency > 0:
            api_environment["CROSS_ENCODER_RERANKER_FUNCTION_NAME"] = (
                reranker_invoke_target.function_arn
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
            timeout=Duration.seconds(90),
            memory_size=2048,
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
        # Free Gateway Endpoints keep S3 / DynamoDB traffic on AWS's backbone
        # instead of egressing through the public NIC. No NAT cost since we
        # already have public subnets only, but this still cuts latency and
        # makes the architecture diagram read more cleanly.
        vpc.add_gateway_endpoint("S3Endpoint", service=ec2.GatewayVpcEndpointAwsService.S3)
        vpc.add_gateway_endpoint(
            "DynamoDBEndpoint", service=ec2.GatewayVpcEndpointAwsService.DYNAMODB
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
        # ListTasks is scoped via the cluster condition; RunTask is scoped to the
        # specific task-definition family (any revision).
        task_def_family_arn = (
            f"arn:aws:ecs:{self.region}:{self.account}:task-definition/{worker_task.family}:*"
        )
        dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ecs:ListTasks"],
                resources=["*"],
                conditions={"ArnEquals": {"ecs:cluster": cluster.cluster_arn}},
            )
        )
        dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ecs:RunTask"],
                resources=[task_def_family_arn],
                conditions={"ArnEquals": {"ecs:cluster": cluster.cluster_arn}},
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
            cloudwatch.GraphWidget(
                title="Reranker latency",
                left=[reranker_function.metric_duration()],
                right=[reranker_function.metric_errors()],
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
        cloudwatch.Alarm(
            self,
            "RerankerErrorAlarm",
            metric=reranker_function.metric_errors(period=Duration.minutes(5)),
            threshold=1,
            evaluation_periods=1,
            alarm_description="The cross-encoder reranker Lambda returned errors.",
        )

        api_logs.add_metric_filter(
            "ApiRequestMetricFilter",
            filter_pattern=logs.FilterPattern.literal("api_request"),
            metric_namespace="VideoRag",
            metric_name="ApiRequestLogLines",
            metric_value="1",
        )
        # Real pipeline failures vs legitimate weak-evidence refusals; without
        # these counters the dashboard can't distinguish "Pinecone down" from
        # "user asked an off-domain question."
        api_logs.add_metric_filter(
            "SearchPipelineErrorMetricFilter",
            filter_pattern=logs.FilterPattern.literal("search_pipeline_error"),
            metric_namespace="VideoRag",
            metric_name="SearchPipelineErrors",
            metric_value="1",
        )
        api_logs.add_metric_filter(
            "BedrockAnswerErrorMetricFilter",
            filter_pattern=logs.FilterPattern.literal("bedrock_answer_error"),
            metric_namespace="VideoRag",
            metric_name="BedrockAnswerErrors",
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
        CfnOutput(self, "RerankerFunctionName", value=reranker_function.function_name)
        CfnOutput(self, "RerankerInvokeTargetArn", value=reranker_invoke_target.function_arn)
        CfnOutput(self, "ApiUrl", value=http_api.url or "")
        CfnOutput(self, "WorkerClusterName", value=cluster.cluster_name)
        CfnOutput(self, "WorkerTaskDefinitionArn", value=worker_task.task_definition_arn)
        CfnOutput(self, "RuntimeSecretName", value=runtime_secret_name)
