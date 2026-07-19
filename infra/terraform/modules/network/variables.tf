variable "name_prefix" {
  description = "Prefix applied to all resource names in this module (e.g. \"vaultly-staging\")."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "Availability zones to spread subnets across. Exactly 2 for the current design."
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the public subnets, one per AZ (ALB + NAT gateways live here)."
  type        = list(string)
  default     = ["10.0.0.0/24", "10.0.1.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for the private subnets, one per AZ (ECS tasks, RDS, ElastiCache live here)."
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "single_nat_gateway" {
  description = "If true, create one NAT gateway (cheaper, single point of failure) instead of one per AZ. Recommended true for staging, false for prod."
  type        = bool
  default     = true
}

variable "app_container_port_api" {
  description = "Container port the api service listens on, opened from the ALB security group into the app security group."
  type        = number
  default     = 8000
}

variable "app_container_port_web" {
  description = "Container port the web service listens on, opened from the ALB security group into the app security group."
  type        = number
  default     = 3000
}

variable "db_port" {
  description = "PostgreSQL port, opened from the app security group into the database security group."
  type        = number
  default     = 5432
}

variable "redis_port" {
  description = "Redis port, opened from the app security group into the redis security group."
  type        = number
  default     = 6379
}

variable "tags" {
  description = "Additional tags to merge onto every resource in this module."
  type        = map(string)
  default     = {}
}
