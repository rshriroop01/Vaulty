variable "name_prefix" {
  description = "Prefix applied to all resource names in this module (e.g. \"vaultly-staging\")."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID the DB subnet group is created in."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs (>= 2, across AZs) for the DB subnet group."
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID to attach to the RDS instance (allows app tier ingress)."
  type        = string
}

variable "engine_version" {
  description = "PostgreSQL engine version."
  type        = string
  default     = "16.4"
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage_gb" {
  description = "Initial allocated storage in GB."
  type        = number
  default     = 20
}

variable "max_allocated_storage_gb" {
  description = "Upper bound for RDS storage autoscaling, in GB."
  type        = number
  default     = 100
}

variable "database_name" {
  description = "Name of the default database created on the instance."
  type        = string
  default     = "vaultly"
}

variable "master_username" {
  description = "Master username for the RDS instance. The password is generated and stored in Secrets Manager, never in state as a variable."
  type        = string
  default     = "vaultly"
}

variable "multi_az" {
  description = "Enable Multi-AZ standby for automatic failover. true in prod, false in staging."
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  description = "Number of days to retain automated backups. 30 for prod, shorter acceptable for staging."
  type        = number
  default     = 30
}

variable "backup_window" {
  description = "Preferred daily backup window (UTC)."
  type        = string
  default     = "06:00-07:00"
}

variable "maintenance_window" {
  description = "Preferred weekly maintenance window (UTC)."
  type        = string
  default     = "sun:07:30-sun:08:30"
}

variable "deletion_protection" {
  description = "Prevent accidental deletion of the RDS instance via the AWS API/console."
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Skip the final snapshot on destroy. Keep false for prod; true is convenient for disposable staging."
  type        = bool
  default     = false
}

variable "performance_insights_enabled" {
  description = "Enable Performance Insights (free tier: 7-day retention)."
  type        = bool
  default     = true
}

variable "apply_immediately" {
  description = "Apply modifications immediately instead of during the next maintenance window. Handy for staging, risky for prod."
  type        = bool
  default     = false
}

variable "monitoring_interval_seconds" {
  description = "Enhanced monitoring granularity in seconds. 0 disables enhanced monitoring."
  type        = number
  default     = 0
}

variable "tags" {
  description = "Additional tags to merge onto every resource in this module."
  type        = map(string)
  default     = {}
}
