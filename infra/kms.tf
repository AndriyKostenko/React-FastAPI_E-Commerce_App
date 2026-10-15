# Data encryption: the private bucket, backups and the Vault snapshots.
resource "aws_kms_key" "data" {
  description             = "${var.name} data: private media, backups"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_kms_alias" "data" {
  name          = "alias/${var.name}-data"
  target_key_id = aws_kms_key.data.key_id
}

# Vault auto-unseal: only the host's role may use it (iam.tf).
resource "aws_kms_key" "vault_unseal" {
  description             = "${var.name} Vault auto-unseal"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_kms_alias" "vault_unseal" {
  name          = "alias/${var.name}-vault-unseal"
  target_key_id = aws_kms_key.vault_unseal.key_id
}
