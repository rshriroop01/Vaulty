variable "name_prefix" {
  description = "Prefix applied to all resource names in this module (e.g. \"vaultly-staging\")."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs (>= 2, across AZs) for the cache subnet group."
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID to attach to the cache cluster (allows app tier ingress)."
  type        = string
}

variable "engine_version" {
  description = "Redis engine version."
  type        = string
  default     = "7.1"
}

variable "node_type" {
  description = "ElastiCache node instance type."
  type        = string
  default     = "cache.t4g.micro"
}

variable "replication_enabled" {
  description = "If true, create a replication group with a read replica + automatic failover (prod). If false, a single node with no replica (staging)."
  type        = bool
  default     = false
}

variable "num_replicas" {
  description = "Number of replica nodes when replication_enabled is true."
  type        = number
  default     = 1
}

variable "port" {
  description = "Port Redis listens on."
  type        = number
  default     = 6379
}

variable "snapshot_retention_days" {
  description = "Number of days to retain automatic snapshots. 0 disables snapshotting (fine for staging cache-only use)."
  type        = number
  default     = 0
}

variable "at_rest_encryption_enabled" {
  description = "Enable encryption at rest."
  type        = bool
  default     = true
}

variable "transit_encryption_enabled" {
  description = "Enable in-transit (TLS) encryption. Requires the app to connect with rediss:// / ssl_cert_reqs configured."
  type        = bool
  default     = true
}

variable "automatic_failover_enabled" {
  description = "Enable automatic failover to a replica. Requires replication_enabled = true and num_replicas >= 1."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags to merge onto every resource in this module."
  type        = map(string)
  default     = {}
}
