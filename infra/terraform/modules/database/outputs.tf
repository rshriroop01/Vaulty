output "instance_id" {
  description = "RDS instance identifier."
  value       = aws_db_instance.this.id
}

output "endpoint" {
  description = "Connection endpoint (host:port)."
  value       = aws_db_instance.this.endpoint
}

output "address" {
  description = "Hostname of the RDS instance, without port."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "Port the RDS instance listens on."
  value       = aws_db_instance.this.port
}

output "database_name" {
  description = "Default database name."
  value       = aws_db_instance.this.db_name
}

output "master_username" {
  description = "Master username (not the password)."
  value       = aws_db_instance.this.username
}

output "master_user_secret_arn" {
  description = "ARN of the RDS-managed Secrets Manager secret holding the master password. Reference this from the app module / task definitions; Terraform never handles the plaintext value."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}
