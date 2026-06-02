# infra

AWS infrastructure as code, using **AWS CDK (Python)**. `CoreStack` provisions
the async-ingestion backbone: an S3 artifacts bucket, an SQS job queue + DLQ,
DynamoDB tables (`videos`, `jobs`), CloudWatch log groups, and scoped IAM roles
for the worker and API.

## Setup

```bash
cd infra
uv venv .venv --python 3.12
uv pip install --python .venv -r requirements.txt
```

## Usage

```bash
cdk synth                 # render CloudFormation (no AWS changes)
cdk bootstrap             # one-time per account/region
cdk deploy                # provision resources
cdk destroy               # tear everything down
```

Stack outputs (bucket name, queue URL, table names) are printed on deploy and
go into the root `.env` (`S3_BUCKET`, `SQS_QUEUE_URL`).
