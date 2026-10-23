# One repository per image, named ecommerce-<service>. Tags are git SHAs, so
# they are immutable: a pushed tag is never overwritten.
locals {
  images = toset([
    "admin-js-service", "api-gateway", "cart-consumer", "cart-service", "frontend",
    "notification-consumer", "notification-service", "notification-taskiq-scheduler", "notification-taskiq-worker",
    "order-consumer", "order-outbox-worker", "order-saga-timeout-worker", "order-service",
    "payment-consumer", "payment-outbox-worker", "payment-service",
    "product-consumer", "product-outbox-worker", "product-service", "product-taskiq-scheduler", "product-taskiq-worker",
    "shipping-consumer", "shipping-outbox-worker", "shipping-service",
    "supplier-consumer", "supplier-outbox-worker", "supplier-service",
    "supplier-taskiq-scheduler", "supplier-taskiq-worker",
    "user-outbox-worker", "user-service", "wishlist-consumer", "wishlist-service",
  ])
}

resource "aws_ecr_repository" "services" {
  for_each = local.images

  name                 = "ecommerce-${each.value}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "services" {
  for_each   = aws_ecr_repository.services
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the 20 most recent images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}
