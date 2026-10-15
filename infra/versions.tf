terraform {
  required_version = ">= 1.8"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Bucket created by bootstrap/. use_lockfile needs no DynamoDB table.
  backend "s3" {
    bucket       = "ecommerce-tfstate-008897528825"
    key          = "production/terraform.tfstate"
    region       = "ca-central-1"
    encrypt      = true
    use_lockfile = true
  }
}
