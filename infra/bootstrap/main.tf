# Run once, by the owner, before the main stack: creates the bucket that holds
# the main stack's state. Its own state stays local (terraform.tfstate here,
# git-ignored): it only holds this one bucket.
#
#   cd infra/bootstrap && tofu init && tofu apply

terraform {
  required_version = ">= 1.8"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

variable "account_id" {
  type    = string
  default = "008897528825"
}

variable "region" {
  type    = string
  default = "ca-central-1"
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]
}

resource "aws_s3_bucket" "tfstate" {
  bucket = "ecommerce-tfstate-${var.account_id}"

  # The state is the map of the whole account: never destroy it by accident.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.tfstate.arn, "${aws_s3_bucket.tfstate.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.tfstate]
}

output "state_bucket" {
  value = aws_s3_bucket.tfstate.id
}
