variable "aws_region" {
  description = "AWS region for the production environment."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name, used in tags and the ENVIRONMENT container env var."
  type        = string
  default     = "production"
}

variable "name_prefix" {
  description = "Prefix applied to all resource names."
  type        = string
  default     = "vaultly-prod"
}

variable "azs" {
  description = "Two availability zones to spread subnets across."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "vpc_cidr" {
  description = "CIDR block for the production VPC."
  type        = string
  default     = "10.20.0.0/16"
}

# --- DNS ---

variable "web_domain_name" {
  description = "Domain the production web app is served on."
  type        = string
  default     = "vaultly.example.com"
}

variable "api_domain_name" {
  description = "Domain the production API is served on."
  type        = string
  default     = "api.vaultly.example.com"
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID covering vaultly.example.com. Assumed to already exist — this stack does not create the zone. Required for ACM DNS validation, SES DKIM, and alias records."
  type        = string
}

# --- Container images ---

variable "image_web" {
  description = "Full image URI for the web service (e.g. \"<account>.dkr.ecr.<region>.amazonaws.com/vaultly-prod/web:<tag>\"). Push via the ECR repos this stack creates, or point at externally-managed repos with create_ecr_repositories = false."
  type        = string
}

variable "image_api" {
  description = "Full image URI for the api service (also used by worker/beat unless overridden)."
  type        = string
}

# --- Email ---

variable "email_from" {
  description = "Verified From address for outbound email, on the SES-verified domain."
  type        = string
  default     = "reminders@vaultly.example.com"
}

variable "ses_domain" {
  description = "Domain to verify in SES for production."
  type        = string
  default     = "vaultly.example.com"
}

# --- CORS (presigned browser uploads) ---

variable "cors_allowed_origins" {
  description = "Origins allowed to PUT directly to presigned S3 URLs."
  type        = list(string)
  default     = ["https://vaultly.example.com"]
}
