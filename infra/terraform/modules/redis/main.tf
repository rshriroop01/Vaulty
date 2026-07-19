# ElastiCache Redis 7. Uses a single replication-group resource for both modes:
# staging runs it as a single node (replication_enabled = false), prod turns on
# a replica + automatic failover (replication_enabled = true).

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name_prefix}-redis-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-redis-subnet-group"
  })
}

resource "aws_elasticache_parameter_group" "this" {
  name   = "${var.name_prefix}-redis7"
  family = "redis7"

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-redis7"
  })
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${var.name_prefix}-redis"
  description          = "Vaultly Redis (Celery broker/result backend + app cache) for ${var.name_prefix}"

  engine         = "redis"
  engine_version = var.engine_version
  node_type      = var.node_type
  port           = var.port

  parameter_group_name = aws_elasticache_parameter_group.this.name
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = [var.security_group_id]

  num_cache_clusters         = var.replication_enabled ? 1 + var.num_replicas : 1
  automatic_failover_enabled = var.replication_enabled ? var.automatic_failover_enabled : false
  multi_az_enabled           = var.replication_enabled ? var.automatic_failover_enabled : false

  at_rest_encryption_enabled = var.at_rest_encryption_enabled
  transit_encryption_enabled = var.transit_encryption_enabled

  snapshot_retention_limit = var.snapshot_retention_days
  snapshot_window          = "05:00-06:00"
  maintenance_window       = "sun:06:30-sun:07:30"

  auto_minor_version_upgrade = true

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-redis"
  })
}
