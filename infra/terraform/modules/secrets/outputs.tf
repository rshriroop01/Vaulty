output "secret_arns" {
  description = "Map of logical secret key -> Secrets Manager ARN, for wiring into ECS task definition secrets[] blocks."
  value       = { for k, s in aws_secretsmanager_secret.app : k => s.arn }
}

output "secret_names" {
  description = "Map of logical secret key -> full Secrets Manager secret name."
  value       = { for k, s in aws_secretsmanager_secret.app : k => s.name }
}
