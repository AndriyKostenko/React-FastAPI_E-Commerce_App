# Only when a domain is set. The registrar must point the domain at the name
# servers in the `dns_name_servers` output (one-time, by hand).
locals {
  dns_enabled = var.domain_name != ""
}

resource "aws_route53_zone" "main" {
  count = local.dns_enabled ? 1 : 0
  name  = var.domain_name
}

resource "aws_route53_record" "apex" {
  count   = local.dns_enabled ? 1 : 0
  zone_id = aws_route53_zone.main[0].zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [aws_eip.host.public_ip]
}

resource "aws_route53_record" "www" {
  count   = local.dns_enabled ? 1 : 0
  zone_id = aws_route53_zone.main[0].zone_id
  name    = "www.${var.domain_name}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.host.public_ip]
}

# External uptime check: sees the whole host going down, which on-host
# monitoring cannot report. Goes through /health on the gateway.
resource "aws_route53_health_check" "storefront" {
  count             = local.dns_enabled ? 1 : 0
  fqdn              = var.domain_name
  type              = "HTTPS"
  port              = 443
  resource_path     = "/health"
  request_interval  = 30
  failure_threshold = 3
  measure_latency   = false

  tags = { Name = "${var.name}-storefront" }
}
