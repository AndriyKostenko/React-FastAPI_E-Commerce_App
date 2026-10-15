data "aws_availability_zones" "available" {
  state = "available"
}

# One public subnet, one host, no NAT gateway (it would cost more than the host).
# Outbound traffic (Stripe, CJ, OpenRouter, SMTP, SSM) goes through the internet
# gateway; nothing inbound except 80/443.
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.name}-igw" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = false

  tags = { Name = "${var.name}-public" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${var.name}-public" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# No SSH. Shell access is Session Manager (SSM), which needs no inbound port.
resource "aws_security_group" "host" {
  name        = "${var.name}-host"
  description = "Storefront host: HTTP and HTTPS in, anything out."
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.name}-host" }
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  security_group_id = aws_security_group.host.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  description       = "HTTPS (Traefik)"
}

resource "aws_vpc_security_group_ingress_rule" "http" {
  security_group_id = aws_security_group.host.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  description       = "HTTP, redirected to HTTPS by Traefik"
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.host.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Stripe, CJ, OpenRouter, SMTP, SSM, ECR"
}

resource "aws_eip" "host" {
  domain = "vpc"
  tags   = { Name = "${var.name}-host" }
}

resource "aws_eip_association" "host" {
  instance_id   = aws_instance.host.id
  allocation_id = aws_eip.host.id
}
