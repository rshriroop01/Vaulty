# Production: multi-AZ RDS, Redis replication + automatic failover, deletion
# protection on, 30-day backup retention, two NAT gateways for AZ-independent
# egress. Same modules as staging — only sizing/HA toggles differ.

locals {
  common_tags = {
    project    = "vaultly"
    env        = var.environment
    managed-by = "terraform"
  }
}

module "network" {
  source = "../../modules/network"

  name_prefix        = var.name_prefix
  vpc_cidr           = var.vpc_cidr
  azs                = var.azs
  single_nat_gateway = false # prod: one NAT per AZ so a single AZ outage doesn't take egress down cluster-wide
  tags               = local.common_tags
}

module "storage" {
  source = "../../modules/storage"

  bucket_name          = "${var.name_prefix}-documents"
  cors_allowed_origins = var.cors_allowed_origins

  noncurrent_version_expiration_days = 90
  noncurrent_version_transition_days = 30

  tags = local.common_tags
}

module "database" {
  source = "../../modules/database"

  name_prefix       = var.name_prefix
  vpc_id            = module.network.vpc_id
  subnet_ids        = module.network.private_subnet_ids
  security_group_id = module.network.database_security_group_id

  instance_class               = "db.r6g.large"
  multi_az                     = true
  backup_retention_days        = 30
  deletion_protection          = true
  skip_final_snapshot          = false
  performance_insights_enabled = true
  monitoring_interval_seconds  = 60
  apply_immediately            = false

  tags = local.common_tags
}

module "redis" {
  source = "../../modules/redis"

  name_prefix       = var.name_prefix
  subnet_ids        = module.network.private_subnet_ids
  security_group_id = module.network.redis_security_group_id

  node_type                  = "cache.r6g.large"
  replication_enabled        = true
  num_replicas               = 1
  automatic_failover_enabled = true
  snapshot_retention_days    = 7

  tags = local.common_tags
}

module "email" {
  source = "../../modules/email"

  domain              = var.ses_domain
  route53_zone_id     = var.route53_zone_id
  mail_from_subdomain = "mail"
  create_dmarc_record = true
  dmarc_policy        = "quarantine" # prod: enforce once staging's monitoring period looks clean

  tags = local.common_tags
}

module "secrets" {
  source = "../../modules/secrets"

  name_prefix          = "vaultly/${var.environment}"
  recovery_window_days = 30 # prod: guard against accidental deletion

  tags = local.common_tags
}

module "app" {
  source = "../../modules/app"

  name_prefix = var.name_prefix
  environment = var.environment
  aws_region  = var.aws_region

  vpc_id                = module.network.vpc_id
  public_subnet_ids     = module.network.public_subnet_ids
  private_subnet_ids    = module.network.private_subnet_ids
  alb_security_group_id = module.network.alb_security_group_id
  app_security_group_id = module.network.app_security_group_id

  web_domain_name    = var.web_domain_name
  api_domain_name    = var.api_domain_name
  route53_zone_id    = var.route53_zone_id
  create_certificate = true
  create_dns_records = true

  documents_bucket_name   = module.storage.bucket_id
  documents_bucket_arn    = module.storage.bucket_arn
  ses_domain_identity_arn = module.email.domain_identity_arn
  email_from              = var.email_from

  db_address                = module.database.address
  db_port                   = module.database.port
  db_name                   = module.database.database_name
  db_master_username        = module.database.master_username
  db_master_user_secret_arn = module.database.master_user_secret_arn

  redis_endpoint_address = module.redis.primary_endpoint_address
  redis_port             = module.redis.port
  redis_tls_enabled      = true

  app_secret_arns = module.secrets.secret_arns

  image_web = var.image_web
  image_api = var.image_api

  # Prod: real headroom, wider autoscaling ceilings for the 10k-user Year-1 target.
  web_cpu       = 512
  web_memory    = 1024
  api_cpu       = 1024
  api_memory    = 2048
  worker_cpu    = 1024
  worker_memory = 2048
  beat_cpu      = 256
  beat_memory   = 512

  web_desired_count    = 2
  api_desired_count    = 2
  worker_desired_count = 2

  web_autoscaling_min    = 2
  web_autoscaling_max    = 6
  api_autoscaling_min    = 2
  api_autoscaling_max    = 8
  worker_autoscaling_min = 2
  worker_autoscaling_max = 10

  log_retention_days = 90

  tags = local.common_tags
}
