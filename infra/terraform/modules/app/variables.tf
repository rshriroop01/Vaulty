variable "name_prefix" {
  description = "Prefix applied to all resource names in this module (e.g. \"vaultly-staging\")."
  type        = string
}

variable "environment" {
  description = "Deployment environment name, passed through as the ENVIRONMENT container env var (e.g. \"staging\", \"production\")."
  type        = string
}

variable "aws_region" {
  description = "AWS region, used to build regional service endpoints (S3, SES SMTP)."
  type        = string
}

# --- Networking (from the network module) ---

variable "vpc_id" {
  description = "VPC ID."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for the ALB."
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for the ECS Fargate tasks."
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "Security group ID for the ALB."
  type        = string
}

variable "app_security_group_id" {
  description = "Security group ID for the ECS Fargate tasks."
  type        = string
}

# --- DNS / TLS ---

variable "web_domain_name" {
  description = "Domain the web app is served on (e.g. \"app.vaultly.com\" or \"staging.vaultly.com\"). Used for the ALB host-based listener rule and, if route53_zone_id is set, an alias record."
  type        = string
}

variable "api_domain_name" {
  description = "Domain the API is served on (e.g. \"api.vaultly.com\" or \"api.staging.vaultly.com\"). Used for the ALB host-based listener rule and, if route53_zone_id is set, an alias record."
  type        = string
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID covering both web_domain_name and api_domain_name. Required when create_certificate is true or create_dns_records is true; leave null to skip DNS/cert automation and supply certificate_arn manually."
  type        = string
  default     = null
}

variable "create_certificate" {
  description = "If true, create and DNS-validate an ACM certificate covering web_domain_name and api_domain_name (requires route53_zone_id). If false, certificate_arn must be supplied."
  type        = bool
  default     = true
}

variable "certificate_arn" {
  description = "Existing ACM certificate ARN to use when create_certificate is false."
  type        = string
  default     = null
}

variable "create_dns_records" {
  description = "If true, create Route53 alias A records pointing web_domain_name and api_domain_name at the ALB (requires route53_zone_id)."
  type        = bool
  default     = true
}

# --- Backing services wiring (plain, non-secret config) ---

variable "documents_bucket_name" {
  description = "S3 documents bucket name (from the storage module), wired in as S3_BUCKET."
  type        = string
}

variable "documents_bucket_arn" {
  description = "S3 documents bucket ARN (from the storage module), used to scope the task role's S3 IAM policy."
  type        = string
}

variable "ses_domain_identity_arn" {
  description = "SES domain identity ARN (from the email module), used to scope the task role's ses:SendEmail policy."
  type        = string
}

variable "email_from" {
  description = "Verified From address for outbound email (must be on the SES-verified domain)."
  type        = string
}

variable "db_address" {
  description = "RDS instance hostname (from the database module)."
  type        = string
}

variable "db_port" {
  description = "RDS instance port (from the database module)."
  type        = number
}

variable "db_name" {
  description = "Default database name (from the database module)."
  type        = string
}

variable "db_master_username" {
  description = "Master DB username (from the database module)."
  type        = string
}

variable "db_master_user_secret_arn" {
  description = "ARN of the RDS-managed Secrets Manager secret holding the master password (from the database module). The api/worker/beat containers read the \"password\" JSON key out of it directly."
  type        = string
}

variable "redis_endpoint_address" {
  description = "ElastiCache primary endpoint hostname (from the redis module)."
  type        = string
}

variable "redis_port" {
  description = "ElastiCache port (from the redis module)."
  type        = number
}

variable "redis_tls_enabled" {
  description = "Whether Redis has transit encryption enabled, controlling whether REDIS_URL uses redis:// or rediss://."
  type        = bool
  default     = true
}

# --- Secrets Manager wiring ---

variable "app_secret_arns" {
  description = <<-EOT
    Map of logical secret key -> Secrets Manager ARN (from the secrets module
    output `secret_arns`). Expected keys: secret-key, anthropic-api-key,
    stripe-secret-key, stripe-webhook-secret, stripe-price-premium,
    stripe-price-family, s3-access-key, s3-secret-key. Missing keys simply
    result in that env var being omitted from the task definition.
  EOT
  type        = map(string)
}

# --- Container images ---

variable "image_web" {
  description = "Full image URI (repo:tag or repo@digest) for the web service."
  type        = string
}

variable "image_api" {
  description = "Full image URI for the api service."
  type        = string
}

variable "image_worker" {
  description = "Full image URI for the worker service. Defaults to image_api (same codebase, different Celery command) when null."
  type        = string
  default     = null
}

variable "image_beat" {
  description = "Full image URI for the beat service. Defaults to image_api when null."
  type        = string
  default     = null
}

variable "create_ecr_repositories" {
  description = "If true, create ECR repositories for the web and api images (worker/beat reuse the api repo). If false, image URIs are assumed to point at externally-managed repositories."
  type        = bool
  default     = true
}

variable "ecr_image_tag_mutability" {
  description = "IMMUTABLE (recommended for prod) or MUTABLE."
  type        = string
  default     = "IMMUTABLE"
}

variable "ecr_untagged_image_expiry_days" {
  description = "Days after which untagged ECR images are expired by lifecycle policy."
  type        = number
  default     = 14
}

# --- ECS Fargate sizing ---

variable "log_retention_days" {
  description = "CloudWatch Logs retention for all service log groups."
  type        = number
  default     = 30
}

variable "container_insights_enabled" {
  description = "Enable ECS Container Insights on the cluster."
  type        = bool
  default     = true
}

variable "web_cpu" {
  description = "Fargate task CPU units for the web service."
  type        = number
  default     = 256
}

variable "web_memory" {
  description = "Fargate task memory (MiB) for the web service."
  type        = number
  default     = 512
}

variable "api_cpu" {
  description = "Fargate task CPU units for the api service."
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "Fargate task memory (MiB) for the api service."
  type        = number
  default     = 1024
}

variable "worker_cpu" {
  description = "Fargate task CPU units for the worker service."
  type        = number
  default     = 512
}

variable "worker_memory" {
  description = "Fargate task memory (MiB) for the worker service."
  type        = number
  default     = 1024
}

variable "beat_cpu" {
  description = "Fargate task CPU units for the beat service."
  type        = number
  default     = 256
}

variable "beat_memory" {
  description = "Fargate task memory (MiB) for the beat service."
  type        = number
  default     = 512
}

variable "web_desired_count" {
  description = "Initial/baseline desired task count for web."
  type        = number
  default     = 1
}

variable "api_desired_count" {
  description = "Initial/baseline desired task count for api."
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "Initial/baseline desired task count for worker."
  type        = number
  default     = 1
}

variable "web_autoscaling_min" {
  description = "Minimum web task count for autoscaling."
  type        = number
  default     = 1
}

variable "web_autoscaling_max" {
  description = "Maximum web task count for autoscaling."
  type        = number
  default     = 3
}

variable "api_autoscaling_min" {
  description = "Minimum api task count for autoscaling."
  type        = number
  default     = 1
}

variable "api_autoscaling_max" {
  description = "Maximum api task count for autoscaling."
  type        = number
  default     = 4
}

variable "worker_autoscaling_min" {
  description = "Minimum worker task count for autoscaling."
  type        = number
  default     = 1
}

variable "worker_autoscaling_max" {
  description = "Maximum worker task count for autoscaling."
  type        = number
  default     = 5
}

variable "autoscaling_cpu_target_percent" {
  description = "Target average CPU utilization percent for target-tracking autoscaling policies."
  type        = number
  default     = 60
}

variable "health_check_path_api" {
  description = "ALB target group health check path for the api service."
  type        = string
  default     = "/healthz"
}

variable "health_check_path_web" {
  description = "ALB target group health check path for the web service."
  type        = string
  default     = "/"
}

variable "assign_public_ip" {
  description = "Assign a public IP to tasks. Should stay false — tasks run in private subnets and reach the internet via NAT."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags to merge onto every resource in this module."
  type        = map(string)
  default     = {}
}
