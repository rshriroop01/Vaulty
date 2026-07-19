output "cluster_id" {
  description = "ECS cluster ID."
  value       = aws_ecs_cluster.this.id
}

output "cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.this.name
}

output "alb_dns_name" {
  description = "ALB DNS name (useful before DNS records propagate)."
  value       = aws_lb.this.dns_name
}

output "alb_arn" {
  description = "ALB ARN."
  value       = aws_lb.this.arn
}

output "alb_zone_id" {
  description = "ALB hosted zone ID (for alias records)."
  value       = aws_lb.this.zone_id
}

output "certificate_arn" {
  description = "ACM certificate ARN in use on the HTTPS listener."
  value       = local.certificate_arn
}

output "ecr_web_repository_url" {
  description = "ECR repository URL for the web image, if created by this module."
  value       = var.create_ecr_repositories ? aws_ecr_repository.web[0].repository_url : null
}

output "ecr_api_repository_url" {
  description = "ECR repository URL for the api image (also used by worker/beat), if created by this module."
  value       = var.create_ecr_repositories ? aws_ecr_repository.api[0].repository_url : null
}

output "execution_role_arn" {
  description = "ECS task execution role ARN."
  value       = aws_iam_role.execution.arn
}

output "task_role_arn" {
  description = "ECS task role ARN (application runtime identity)."
  value       = aws_iam_role.task.arn
}

output "migrate_task_definition_arn" {
  description = "Task definition ARN for the one-off migration task (run via `aws ecs run-task`, not a standing service)."
  value       = aws_ecs_task_definition.migrate.arn
}

output "service_names" {
  description = "Map of logical service name -> ECS service name."
  value = {
    web    = aws_ecs_service.web.name
    api    = aws_ecs_service.api.name
    worker = aws_ecs_service.worker.name
    beat   = aws_ecs_service.beat.name
  }
}
