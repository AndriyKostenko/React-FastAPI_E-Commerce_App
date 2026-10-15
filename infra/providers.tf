locals {
  common_tags = {
    Project     = var.name
    Environment = "production"
    ManagedBy   = "opentofu"
  }
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]

  default_tags {
    tags = local.common_tags
  }
}

# CloudFront certificates and its alarms must live in us-east-1.
provider "aws" {
  alias               = "us_east_1"
  region              = "us-east-1"
  allowed_account_ids = [var.account_id]

  default_tags {
    tags = local.common_tags
  }
}
