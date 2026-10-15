variable "account_id" {
  description = "The only AWS account this stack may touch."
  type        = string
  default     = "008897528825"
}

variable "region" {
  type    = string
  default = "ca-central-1"
}

variable "name" {
  description = "Prefix for resource names."
  type        = string
  default     = "ecommerce"
}

variable "domain_name" {
  description = "Apex domain of the storefront (e.g. example.ca). Empty = no DNS, CDN or uptime check yet."
  type        = string
  default     = ""
}

variable "alert_email" {
  description = "Where alarms and the budget warning go. Empty = no subscription."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  type    = number
  default = 100
}

variable "instance_type" {
  description = "Graviton, 2 vCPU / 8 GB, no burst credits."
  type        = string
  default     = "m7g.large"
}

variable "root_volume_gb" {
  type    = number
  default = 80
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "public_subnet_cidr" {
  type    = string
  default = "10.20.1.0/24"
}

variable "github_repository" {
  description = "owner/repo allowed to deploy."
  type        = string
  default     = "AndriyKostenko/React-FastAPI_E-Commerce_App"
}

variable "github_environment" {
  description = "GitHub environment whose approval gates the deploy."
  type        = string
  default     = "production"
}
