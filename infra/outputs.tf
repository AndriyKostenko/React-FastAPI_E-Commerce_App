output "host_instance_id" {
  value = aws_instance.host.id
}

output "host_public_ip" {
  description = "Point the domain here (or it is set by dns.tf)."
  value       = aws_eip.host.public_ip
}

output "ecr_registry" {
  description = "IMAGE_REGISTRY for compose: <this>/ecommerce-<service>."
  value       = "${var.account_id}.dkr.ecr.${var.region}.amazonaws.com"
}

output "deploy_role_arn" {
  description = "Role the GitHub production environment assumes to run the host deploy."
  value       = aws_iam_role.deploy.arn
}

output "build_role_arn" {
  description = "Role the build job assumes to push images to ECR (main only)."
  value       = aws_iam_role.build.arn
}

output "buckets" {
  value = {
    catalogue = aws_s3_bucket.catalogue.id
    private   = aws_s3_bucket.private.id
    backups   = aws_s3_bucket.backups.id
  }
}

output "kms_key_arns" {
  value = {
    data         = aws_kms_key.data.arn
    vault_unseal = aws_kms_key.vault_unseal.arn
  }
}

output "dns_name_servers" {
  description = "Set these at the registrar (one time)."
  value       = local.dns_enabled ? aws_route53_zone.main[0].name_servers : []
}

output "images_host" {
  description = "CATALOGUE_IMAGE_HOST for the storefront build (empty until a domain is set)."
  value       = local.images_host
}

# Long-lived keys for the two services that handle objects. Store them in each
# service's Vault path, then keep the state bucket private. Read with:
#   tofu output -raw product_service_access_key_id
output "product_service_access_key_id" {
  value     = aws_iam_access_key.product_service.id
  sensitive = true
}

output "product_service_secret_access_key" {
  value     = aws_iam_access_key.product_service.secret
  sensitive = true
}

output "order_service_access_key_id" {
  value     = aws_iam_access_key.order_service.id
  sensitive = true
}

output "order_service_secret_access_key" {
  value     = aws_iam_access_key.order_service.secret
  sensitive = true
}
