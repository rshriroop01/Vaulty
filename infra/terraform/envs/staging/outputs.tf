output "alb_dns_name" {
  description = "ALB DNS name."
  value       = module.app.alb_dns_name
}

output "web_url" {
  description = "Public web URL."
  value       = "https://${var.web_domain_name}"
}

output "api_url" {
  description = "Public API URL."
  value       = "https://${var.api_domain_name}"
}

output "database_endpoint" {
  description = "RDS endpoint (host:port)."
  value       = module.database.endpoint
}

output "database_master_user_secret_arn" {
  description = "Secrets Manager ARN holding the RDS-managed master password."
  value       = module.database.master_user_secret_arn
}

output "redis_endpoint" {
  description = "ElastiCache primary endpoint."
  value       = module.redis.primary_endpoint_address
}

output "documents_bucket" {
  description = "S3 documents bucket name."
  value       = module.storage.bucket_id
}

output "ecr_web_repository_url" {
  description = "ECR repo for the web image."
  value       = module.app.ecr_web_repository_url
}

output "ecr_api_repository_url" {
  description = "ECR repo for the api image (also used by worker/beat)."
  value       = module.app.ecr_api_repository_url
}

output "app_secret_arns" {
  description = "Map of logical secret key -> Secrets Manager ARN. Populate these values out-of-band after apply."
  value       = module.secrets.secret_arns
}

output "migrate_task_definition_arn" {
  description = "Task definition ARN for the one-off `alembic upgrade head` task. Run via `aws ecs run-task` before rolling out a new api/worker/beat image."
  value       = module.app.migrate_task_definition_arn
}

output "ses_dkim_tokens" {
  description = "SES DKIM tokens (informational — Terraform already publishes these as Route53 CNAMEs)."
  value       = module.email.dkim_tokens
}
