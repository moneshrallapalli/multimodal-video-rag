"""Core infrastructure for the multimodal video RAG platform.

Defines the async-ingestion backbone: an S3 artifacts bucket, an SQS job
queue with a dead-letter queue, DynamoDB tables for video metadata and job
status, CloudWatch log groups, and scoped IAM roles for the worker and API.
"""

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_dynamodb as ddb,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_sqs as sqs,
)
from constructs import Construct


class CoreStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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

        # CloudWatch log groups (short retention for cost control).
        logs.LogGroup(
            self,
            "ApiLogs",
            log_group_name="/video-rag/api",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )
        logs.LogGroup(
            self,
            "WorkerLogs",
            log_group_name="/video-rag/worker",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # IAM role for the ingestion worker (ECS Fargate task role).
        worker_role = iam.Role(
            self,
            "WorkerRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        artifacts.grant_read_write(worker_role)
        videos.grant_read_write_data(worker_role)
        jobs.grant_read_write_data(worker_role)
        ingest_queue.grant_consume_messages(worker_role)
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
        ingest_queue.grant_send_messages(api_role)
        api_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=["*"],  # TODO: scope to the Claude/Titan model ARNs
            )
        )

        # Outputs — copy the bucket name and queue URL into .env.
        CfnOutput(self, "ArtifactsBucketName", value=artifacts.bucket_name)
        CfnOutput(self, "IngestQueueUrl", value=ingest_queue.queue_url)
        CfnOutput(self, "IngestDlqUrl", value=dlq.queue_url)
        CfnOutput(self, "VideosTableName", value=videos.table_name)
        CfnOutput(self, "JobsTableName", value=jobs.table_name)
        CfnOutput(self, "WorkerRoleArn", value=worker_role.role_arn)
        CfnOutput(self, "ApiRoleArn", value=api_role.role_arn)
