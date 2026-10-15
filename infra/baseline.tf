# ---------------------------------------------------------------------------
# Account baseline. Root MFA and the Identity Center user are done by hand
# (they need the console); see the runbook in PRODUCTION_GAPS §1.
# ---------------------------------------------------------------------------
resource "aws_ebs_encryption_by_default" "on" {
  enabled = true
}

resource "aws_s3_account_public_access_block" "on" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_guardduty_detector" "main" {
  enable = true
}

# Audit trail of every API call in every region.
resource "aws_s3_bucket" "cloudtrail" {
  bucket = "${var.name}-cloudtrail-${var.account_id}"
}

resource "aws_s3_bucket_public_access_block" "cloudtrail" {
  bucket                  = aws_s3_bucket.cloudtrail.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "cloudtrail" {
  bucket     = aws_s3_bucket.cloudtrail.id
  depends_on = [aws_s3_bucket_public_access_block.cloudtrail]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AWSCloudTrailAclCheck"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.cloudtrail.arn
        Condition = {
          StringEquals = { "aws:SourceArn" = "arn:aws:cloudtrail:${var.region}:${var.account_id}:trail/${var.name}-trail" }
        }
      },
      {
        Sid       = "AWSCloudTrailWrite"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.cloudtrail.arn}/AWSLogs/${var.account_id}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl"  = "bucket-owner-full-control"
            "aws:SourceArn" = "arn:aws:cloudtrail:${var.region}:${var.account_id}:trail/${var.name}-trail"
          }
        }
      },
    ]
  })
}

resource "aws_cloudtrail" "main" {
  name                          = "${var.name}-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true

  depends_on = [aws_s3_bucket_policy.cloudtrail]
}

# Alarms and the budget warning go to one email topic (when alert_email is set).
resource "aws_sns_topic" "alerts" {
  name = "${var.name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Route 53 health metrics only exist in us-east-1.
resource "aws_sns_topic" "alerts_us_east_1" {
  provider = aws.us_east_1
  name     = "${var.name}-alerts-uptime"
}

resource "aws_sns_topic_subscription" "alerts_us_east_1_email" {
  provider  = aws.us_east_1
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts_us_east_1.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "host_status" {
  alarm_name          = "${var.name}-host-status-check"
  alarm_description   = "The host failed an EC2 status check."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  dimensions          = { InstanceId = aws_instance.host.id }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

# Whole host unreachable from outside (the external check, see dns.tf).
resource "aws_cloudwatch_metric_alarm" "storefront_down" {
  count               = local.dns_enabled ? 1 : 0
  provider            = aws.us_east_1
  alarm_name          = "${var.name}-storefront-down"
  alarm_description   = "https://${var.domain_name}/health has been failing for 3 minutes."
  namespace           = "AWS/Route53"
  metric_name         = "HealthCheckStatus"
  dimensions          = { HealthCheckId = aws_route53_health_check.storefront[0].id }
  statistic           = "Minimum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_sns_topic.alerts_us_east_1.arn]
  ok_actions          = [aws_sns_topic.alerts_us_east_1.arn]
}

resource "aws_budgets_budget" "monthly" {
  name         = "${var.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = var.alert_email != "" ? [80, 100] : []
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "FORECASTED"
      subscriber_email_addresses = [var.alert_email]
    }
  }
}
