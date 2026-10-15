# ---------------------------------------------------------------------------
# The host: pulls images, writes backups, unseals Vault. Containers cannot use
# this role (IMDS hop limit 1).
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "host" {
  name               = "${var.name}-host"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_instance_profile" "host" {
  name = "${var.name}-host"
  role = aws_iam_role.host.name
}

# Shell and deploy commands go through Session Manager.
resource "aws_iam_role_policy_attachment" "host_ssm" {
  role       = aws_iam_role.host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "host" {
  name = "${var.name}-host"
  role = aws_iam_role.host.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrLogin"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "EcrPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchCheckLayerAvailability",
        ]
        Resource = [for r in values(aws_ecr_repository.services) : r.arn]
      },
      {
        Sid      = "WriteBackups"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.backups.arn, "${aws_s3_bucket.backups.arn}/*"]
      },
      {
        Sid      = "BackupsEncryption"
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey", "kms:Decrypt", "kms:Encrypt"]
        Resource = aws_kms_key.data.arn
      },
      {
        Sid      = "VaultAutoUnseal"
        Effect   = "Allow"
        Action   = ["kms:Encrypt", "kms:Decrypt", "kms:DescribeKey"]
        Resource = aws_kms_key.vault_unseal.arn
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# S3 identities for the services that handle objects, mirroring the local
# ones (local/s3_local.py): product-service on the catalogue and the designs
# prefix, order-service on the return-evidence prefix only (user-service, on
# avatars/, is below). Their keys go into
# each service's Vault path (phase 6), never into the repository.
# ---------------------------------------------------------------------------
resource "aws_iam_user" "product_service" {
  name = "${var.name}-product-service"
}

resource "aws_iam_user" "order_service" {
  name = "${var.name}-order-service"
}

resource "aws_iam_user_policy" "product_service" {
  name = "s3"
  user = aws_iam_user.product_service.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "CatalogueObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.catalogue.arn}/*"
      },
      {
        Sid      = "CatalogueList"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.catalogue.arn
      },
      {
        Sid      = "DesignsObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.private.arn}/generated-designs/*"
      },
      {
        Sid      = "DesignsEncryption"
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey", "kms:Decrypt", "kms:Encrypt"]
        Resource = aws_kms_key.data.arn
      },
    ]
  })
}

resource "aws_iam_user_policy" "order_service" {
  name = "s3"
  user = aws_iam_user.order_service.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReturnEvidenceObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.private.arn}/return-evidence/*"
      },
      {
        Sid      = "ReturnEvidenceEncryption"
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey", "kms:Decrypt", "kms:Encrypt"]
        Resource = aws_kms_key.data.arn
      },
    ]
  })
}

resource "aws_iam_access_key" "product_service" {
  user = aws_iam_user.product_service.name
}

resource "aws_iam_access_key" "order_service" {
  user = aws_iam_user.order_service.name
}

# user-service: its users' avatars, under avatars/ in the public catalogue
# bucket and nowhere else (local/s3_local.py grants the same).
resource "aws_iam_user" "user_service" {
  name = "${var.name}-user-service"
}

resource "aws_iam_user_policy" "user_service" {
  name = "s3"
  user = aws_iam_user.user_service.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AvatarObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.catalogue.arn}/avatars/*"
      },
    ]
  })
}

resource "aws_iam_access_key" "user_service" {
  user = aws_iam_user.user_service.name
}

# ---------------------------------------------------------------------------
# GitHub Actions deploy role: OIDC, no stored keys. Trusted only by the
# production environment of this repository, which requires an approval.
# ---------------------------------------------------------------------------
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

# Two roles, so the approval gate cannot be skipped. The build role pushes
# images from any run on main and can do nothing else. The deploy role can
# run commands on the host, and only the `production` environment (which
# requires an approval) may assume it.
data "aws_iam_policy_document" "build_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "build" {
  name               = "${var.name}-github-build"
  assume_role_policy = data.aws_iam_policy_document.build_trust.json
}

resource "aws_iam_role_policy" "build" {
  name = "push-images"
  role = aws_iam_role.build.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrLogin"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "EcrPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:CompleteLayerUpload",
          "ecr:DescribeImages",
          "ecr:GetDownloadUrlForLayer",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart",
        ]
        Resource = [for r in values(aws_ecr_repository.services) : r.arn]
      },
    ]
  })
}

data "aws_iam_policy_document" "deploy_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:environment:${var.github_environment}"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name               = "${var.name}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.deploy_trust.json
}

resource "aws_iam_role_policy" "deploy" {
  name = "deploy"
  role = aws_iam_role.deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Run commands on the host only; nothing else in the account.
        Sid    = "DeployToHost"
        Effect = "Allow"
        Action = "ssm:SendCommand"
        Resource = [
          aws_instance.host.arn,
          "arn:aws:ssm:${var.region}::document/AWS-RunShellScript",
        ]
      },
      {
        Sid      = "ReadCommandResults"
        Effect   = "Allow"
        Action   = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations"]
        Resource = "*"
      },
    ]
  })
}
