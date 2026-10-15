# Catalogue images: https://images.<domain>/<key>. Requires a domain.
locals {
  images_host = local.dns_enabled ? "images.${var.domain_name}" : ""
}

# CloudFront needs its certificate in us-east-1.
resource "aws_acm_certificate" "images" {
  count             = local.dns_enabled ? 1 : 0
  provider          = aws.us_east_1
  domain_name       = local.images_host
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "images_validation" {
  for_each = local.dns_enabled ? {
    for dvo in aws_acm_certificate.images[0].domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  } : {}

  zone_id         = aws_route53_zone.main[0].zone_id
  name            = each.value.name
  type            = each.value.type
  ttl             = 300
  records         = [each.value.record]
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "images" {
  count                   = local.dns_enabled ? 1 : 0
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.images[0].arn
  validation_record_fqdns = [for r in aws_route53_record.images_validation : r.fqdn]
}

resource "aws_cloudfront_origin_access_control" "catalogue" {
  count                             = local.dns_enabled ? 1 : 0
  name                              = "${var.name}-catalogue"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "images" {
  count               = local.dns_enabled ? 1 : 0
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.name} catalogue images"
  aliases             = [local.images_host]
  price_class         = "PriceClass_100"
  default_root_object = ""

  origin {
    domain_name              = aws_s3_bucket.catalogue.bucket_regional_domain_name
    origin_id                = "catalogue"
    origin_access_control_id = aws_cloudfront_origin_access_control.catalogue[0].id
  }

  default_cache_behavior {
    target_origin_id       = "catalogue"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    # AWS managed "CachingOptimized".
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.images[0].certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

# The catalogue bucket's only policy: refuse plain HTTP, and (once a domain is
# set) let this distribution, and nothing else, read it.
resource "aws_s3_bucket_policy" "catalogue" {
  bucket = aws_s3_bucket.catalogue.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [{
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [aws_s3_bucket.catalogue.arn, "${aws_s3_bucket.catalogue.arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      }],
      local.dns_enabled ? [{
        Sid       = "CloudFrontRead"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.catalogue.arn}/*"
        Condition = {
          StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.images[0].arn }
        }
      }] : [],
    )
  })
  depends_on = [aws_s3_bucket_public_access_block.all]
}

resource "aws_route53_record" "images" {
  count   = local.dns_enabled ? 1 : 0
  zone_id = aws_route53_zone.main[0].zone_id
  name    = local.images_host
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.images[0].domain_name
    zone_id                = aws_cloudfront_distribution.images[0].hosted_zone_id
    evaluate_target_health = false
  }
}
