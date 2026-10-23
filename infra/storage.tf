locals {
  catalogue_bucket = "${var.name}-catalogue-${var.account_id}"
  private_bucket   = "${var.name}-private-${var.account_id}"
  backups_bucket   = "${var.name}-backups-${var.account_id}"
}

# Catalogue: product, variant and category images. Never public: CloudFront
# reads it through Origin Access Control (cdn.tf). Services write it with their
# own keys (iam.tf).
resource "aws_s3_bucket" "catalogue" {
  bucket = local.catalogue_bucket
}

# Private: generated designs and return photos. Presigned URLs only.
resource "aws_s3_bucket" "private" {
  bucket = local.private_bucket
}

# Backups: pg_dump every 6 h, Vault snapshots. Kept 30 days.
resource "aws_s3_bucket" "backups" {
  bucket = local.backups_bucket

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each = {
    catalogue = aws_s3_bucket.catalogue.id
    private   = aws_s3_bucket.private.id
    backups   = aws_s3_bucket.backups.id
  }

  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "all" {
  for_each = {
    catalogue = aws_s3_bucket.catalogue.id
    private   = aws_s3_bucket.private.id
    backups   = aws_s3_bucket.backups.id
  }

  bucket = each.value
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "private" {
  bucket = aws_s3_bucket.private.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "private" {
  bucket = aws_s3_bucket.private.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "catalogue" {
  bucket = aws_s3_bucket.catalogue.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  # Versioning is on, so a dump that is overwritten or deleted stays for 7 days.
  rule {
    id     = "expire-backups"
    status = "Enabled"
    filter {}

    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# Designs and return evidence a service deletes (retention, a deleted
# account) leave a delete marker on the versioned bucket; the old version is
# gone 30 days later, so a mistaken delete can still be undone for a month.
resource "aws_s3_bucket_lifecycle_configuration" "private" {
  bucket = aws_s3_bucket.private.id

  rule {
    id     = "expire-deleted-objects"
    status = "Enabled"
    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    expiration {
      expired_object_delete_marker = true
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# Every bucket refuses plain HTTP.
# The catalogue bucket's policy is in cdn.tf (it also grants CloudFront).
resource "aws_s3_bucket_policy" "deny_insecure" {
  for_each = {
    private = aws_s3_bucket.private.arn
    backups = aws_s3_bucket.backups.arn
  }

  bucket = split(":::", each.value)[1]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [each.value, "${each.value}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })

  depends_on = [aws_s3_bucket_public_access_block.all]
}

# Snapshot every tagged volume (the host's root volume) once a day, keep 7.
resource "aws_iam_role" "dlm" {
  name = "${var.name}-dlm"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "dlm.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "dlm" {
  role       = aws_iam_role.dlm.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}

resource "aws_dlm_lifecycle_policy" "host_snapshots" {
  description        = "${var.name} host root volume daily keep 7"
  execution_role_arn = aws_iam_role.dlm.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["VOLUME"]
    target_tags    = { Backup = "daily" }

    schedule {
      name      = "daily"
      copy_tags = true

      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = ["03:00"]
      }

      retain_rule {
        count = 7
      }
    }
  }
}
