# Amazon Linux 2023 on arm64, looked up from the public SSM parameter.
data "aws_ssm_parameter" "al2023_arm64" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

resource "aws_instance" "host" {
  ami                    = data.aws_ssm_parameter.al2023_arm64.value
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.host.id]
  iam_instance_profile   = aws_iam_instance_profile.host.name

  # No key pair: access is SSM only.
  key_name = null

  # Containers must not reach the host role (hop limit 1 blocks them).
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_gb
    encrypted   = true
    # Tag read by the snapshot policy (storage.tf).
    tags = { Backup = "daily" }
  }

  monitoring              = true
  ebs_optimized           = true
  disable_api_termination = true

  tags = { Name = "${var.name}-host", Role = "storefront" }

  # Replacing the host is a deliberate act (it rebuilds Postgres and Vault data
  # from backups). A newer AMI or changed user data does not trigger it.
  lifecycle {
    ignore_changes = [ami, user_data, user_data_base64]
  }
}
