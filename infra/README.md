# infra

Infrastructure as code for the AWS stack: S3 (artifacts), SQS (+ DLQ),
DynamoDB (videos, jobs), IAM roles, CloudWatch, and the Fargate worker /
Lambda API wiring. Tooling (AWS CDK in Python vs Terraform) is chosen at the
start of the infra phase.
