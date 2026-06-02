#!/usr/bin/env python3
"""CDK app entrypoint for the multimodal video RAG platform."""

import os

import aws_cdk as cdk
from video_rag_infra.core_stack import CoreStack

app = cdk.App()

CoreStack(
    app,
    "VideoRagCore",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
    ),
)

app.synth()
