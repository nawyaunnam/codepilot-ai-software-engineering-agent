terraform { required_version=">= 1.7"; required_providers { aws={source="hashicorp/aws",version="~> 5.0"} } }
provider "aws" {region=var.region}
variable "region" {type=string;default="us-east-1"}
resource "aws_s3_bucket" "repositories" {bucket_prefix="codepilot-repositories-"}
resource "aws_s3_bucket_versioning" "repositories" {bucket=aws_s3_bucket.repositories.id;versioning_configuration{status="Enabled"}}
resource "aws_s3_bucket_server_side_encryption_configuration" "repositories" {bucket=aws_s3_bucket.repositories.id;rule{apply_server_side_encryption_by_default{sse_algorithm="AES256"}}}
resource "aws_sqs_queue" "index_dlq" {name="codepilot-index-dlq";sqs_managed_sse_enabled=true;message_retention_seconds=1209600}
resource "aws_sqs_queue" "index" {name="codepilot-index";sqs_managed_sse_enabled=true;visibility_timeout_seconds=900;redrive_policy=jsonencode({deadLetterTargetArn=aws_sqs_queue.index_dlq.arn,maxReceiveCount=3})}
