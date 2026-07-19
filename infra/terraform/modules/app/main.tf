# ECS Fargate cluster running the four Vaultly services (web, api, worker,
# beat) behind an ALB that host/path-routes to web vs api, with autoscaling
# on web/api/worker (beat is a fixed singleton — Celery beat must never run
# more than one instance or reminders double-send).

locals {
  image_worker = coalesce(var.image_worker, var.image_api)
  image_beat   = coalesce(var.image_beat, var.image_api)

  redis_scheme = var.redis_tls_enabled ? "rediss" : "redis"
  redis_url    = "${local.redis_scheme}://${var.redis_endpoint_address}:${var.redis_port}/0"

  s3_regional_endpoint = "https://s3.${var.aws_region}.amazonaws.com"

  log_group_web     = "/ecs/${var.name_prefix}/web"
  log_group_api     = "/ecs/${var.name_prefix}/api"
  log_group_worker  = "/ecs/${var.name_prefix}/worker"
  log_group_beat    = "/ecs/${var.name_prefix}/beat"
  log_group_migrate = "/ecs/${var.name_prefix}/migrate"

  # Plain (non-secret) env vars shared by api/worker/beat/migrate — everything
  # that touches the database/queue/storage except the DB password.
  backend_common_environment = [
    { name = "ENVIRONMENT", value = var.environment },
    { name = "DEBUG", value = "false" },
    { name = "LOG_LEVEL", value = "INFO" },
    { name = "REDIS_URL", value = local.redis_url },
    { name = "S3_ENDPOINT_URL", value = local.s3_regional_endpoint },
    { name = "S3_PUBLIC_ENDPOINT_URL_OVERRIDE", value = local.s3_regional_endpoint },
    { name = "S3_BUCKET", value = var.documents_bucket_name },
    { name = "SMTP_HOST", value = "email-smtp.${var.aws_region}.amazonaws.com" },
    { name = "SMTP_PORT", value = "587" },
    { name = "EMAIL_FROM", value = var.email_from },
    { name = "DB_HOST", value = var.db_address },
    { name = "DB_PORT", value = tostring(var.db_port) },
    { name = "DB_NAME", value = var.db_name },
    { name = "DB_USER", value = var.db_master_username },
  ]

  # Secrets Manager -> env var wiring for api/worker/beat/migrate. DB_PASSWORD
  # comes straight out of the RDS-managed master secret's "password" JSON key;
  # everything else comes from the secrets module's shells (populated
  # out-of-band). Keys not present in var.app_secret_arns are skipped rather
  # than failing, so envs can stand up the app before every optional secret
  # (e.g. Stripe) is populated.
  optional_secret_env_map = {
    SECRET_KEY            = "secret-key"
    ANTHROPIC_API_KEY     = "anthropic-api-key"
    STRIPE_SECRET_KEY     = "stripe-secret-key"
    STRIPE_WEBHOOK_SECRET = "stripe-webhook-secret"
    STRIPE_PRICE_PREMIUM  = "stripe-price-premium"
    STRIPE_PRICE_FAMILY   = "stripe-price-family"
    S3_ACCESS_KEY         = "s3-access-key"
    S3_SECRET_KEY         = "s3-secret-key"
  }

  backend_common_secrets = concat(
    [
      { name = "DB_PASSWORD", valueFrom = "${var.db_master_user_secret_arn}:password::" },
    ],
    [
      for env_name, secret_key in local.optional_secret_env_map : {
        name      = env_name
        valueFrom = var.app_secret_arns[secret_key]
      }
      if contains(keys(var.app_secret_arns), secret_key)
    ]
  )

  # Builds DATABASE_URL from the split DB_* vars at container start (rather
  # than requiring a pre-composed DATABASE_URL secret) so the RDS-managed
  # password secret can be wired straight in without an out-of-band assembly
  # step. See README "Database URL assembly" for the rationale.
  db_url_export = "export DATABASE_URL=postgresql+asyncpg://$${DB_USER}:$${DB_PASSWORD}@$${DB_HOST}:$${DB_PORT}/$${DB_NAME}"
}

# --- ECS cluster ---

resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = var.container_insights_enabled ? "enabled" : "disabled"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-cluster"
  })
}

# --- ECR repositories (web + api; worker/beat reuse the api image) ---

resource "aws_ecr_repository" "web" {
  count                = var.create_ecr_repositories ? 1 : 0
  name                 = "${var.name_prefix}/web"
  image_tag_mutability = var.ecr_image_tag_mutability

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}/web"
  })
}

resource "aws_ecr_repository" "api" {
  count                = var.create_ecr_repositories ? 1 : 0
  name                 = "${var.name_prefix}/api"
  image_tag_mutability = var.ecr_image_tag_mutability

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}/api"
  })
}

resource "aws_ecr_lifecycle_policy" "web" {
  count      = var.create_ecr_repositories ? 1 : 0
  repository = aws_ecr_repository.web[0].name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = var.ecr_untagged_image_expiry_days
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "api" {
  count      = var.create_ecr_repositories ? 1 : 0
  repository = aws_ecr_repository.api[0].name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = var.ecr_untagged_image_expiry_days
      }
      action = { type = "expire" }
    }]
  })
}

# --- CloudWatch log groups ---

resource "aws_cloudwatch_log_group" "web" {
  name              = local.log_group_web
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "api" {
  name              = local.log_group_api
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = local.log_group_worker
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "beat" {
  name              = local.log_group_beat
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "migrate" {
  name              = local.log_group_migrate
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

# --- IAM: task execution role (pulls image, writes logs, fetches secrets at launch) ---

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    sid       = "ReadAppSecretsAtLaunch"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = concat(values(var.app_secret_arns), [var.db_master_user_secret_arn])
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "${var.name_prefix}-ecs-execution-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets.json
}

# --- IAM: task role (used by the running application code) ---

resource "aws_iam_role" "task" {
  name               = "${var.name_prefix}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "task_permissions" {
  statement {
    sid = "DocumentsBucketObjectAccess"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${var.documents_bucket_arn}/*"]
  }

  statement {
    sid       = "DocumentsBucketListAccess"
    actions   = ["s3:ListBucket"]
    resources = [var.documents_bucket_arn]
  }

  statement {
    sid       = "SendVerifiedEmail"
    actions   = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = [var.ses_domain_identity_arn]
  }

  statement {
    sid       = "ReadAppSecretsAtRuntime"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = concat(values(var.app_secret_arns), [var.db_master_user_secret_arn])
  }
}

resource "aws_iam_role_policy" "task_permissions" {
  name   = "${var.name_prefix}-ecs-task-permissions"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task_permissions.json
}

# --- ACM certificate (optional) ---

resource "aws_acm_certificate" "this" {
  count                     = var.create_certificate ? 1 : 0
  domain_name               = var.web_domain_name
  subject_alternative_names = [var.api_domain_name]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-cert"
  })
}

resource "aws_route53_record" "cert_validation" {
  for_each = var.create_certificate ? {
    for dvo in aws_acm_certificate.this[0].domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  } : {}

  zone_id         = var.route53_zone_id
  name            = each.value.name
  type            = each.value.type
  ttl             = 300
  records         = [each.value.record]
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "this" {
  count                   = var.create_certificate ? 1 : 0
  certificate_arn         = aws_acm_certificate.this[0].arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

locals {
  certificate_arn = var.create_certificate ? aws_acm_certificate.this[0].arn : var.certificate_arn
}

# --- ALB ---

resource "aws_lb" "this" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  drop_invalid_header_fields = true

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-alb"
  })
}

resource "aws_lb_target_group" "web" {
  name        = "${var.name_prefix}-web-tg"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = var.health_check_path_web
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 30

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-web-tg"
  })
}

resource "aws_lb_target_group" "api" {
  name        = "${var.name_prefix}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = var.health_check_path_api
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 30

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-api-tg"
  })
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = local.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }

  depends_on = [aws_acm_certificate_validation.this]
}

# Route by host: api.<domain> -> api target group.
resource "aws_lb_listener_rule" "api_host" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    host_header {
      values = [var.api_domain_name]
    }
  }
}

# Route by path on the web host: <domain>/api/* -> api target group, so the
# web app and API can also share a single origin if the frontend prefers
# same-origin calls.
resource "aws_lb_listener_rule" "api_path_on_web_host" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 20

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    host_header {
      values = [var.web_domain_name]
    }
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}

resource "aws_route53_record" "web_alias" {
  count   = var.create_dns_records ? 1 : 0
  zone_id = var.route53_zone_id
  name    = var.web_domain_name
  type    = "A"

  alias {
    name                   = aws_lb.this.dns_name
    zone_id                = aws_lb.this.zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "api_alias" {
  count   = var.create_dns_records ? 1 : 0
  zone_id = var.route53_zone_id
  name    = var.api_domain_name
  type    = "A"

  alias {
    name                   = aws_lb.this.dns_name
    zone_id                = aws_lb.this.zone_id
    evaluate_target_health = true
  }
}

# --- Task definitions ---

resource "aws_ecs_task_definition" "web" {
  family                   = "${var.name_prefix}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.web_cpu
  memory                   = var.web_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "web"
      image     = var.image_web
      essential = true
      portMappings = [{
        containerPort = 3000
        protocol      = "tcp"
      }]
      environment = [
        { name = "NEXT_PUBLIC_API_URL", value = "https://${var.api_domain_name}" },
        { name = "API_URL_INTERNAL", value = "https://${var.api_domain_name}" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = local.log_group_web
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "web"
        }
      }
    }
  ])

  tags = var.tags
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.image_api
      essential = true
      portMappings = [{
        containerPort = 8000
        protocol      = "tcp"
      }]
      command = [
        "sh", "-c",
        "${local.db_url_export} && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"
      ]
      environment = local.backend_common_environment
      secrets     = local.backend_common_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = local.log_group_api
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])

  tags = var.tags
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = local.image_worker
      essential = true
      command = [
        "sh", "-c",
        "${local.db_url_export} && exec celery -A app.worker.celery_app worker --loglevel INFO"
      ]
      environment = local.backend_common_environment
      secrets     = local.backend_common_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = local.log_group_worker
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])

  tags = var.tags
}

resource "aws_ecs_task_definition" "beat" {
  family                   = "${var.name_prefix}-beat"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.beat_cpu
  memory                   = var.beat_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "beat"
      image     = local.image_beat
      essential = true
      command = [
        "sh", "-c",
        "${local.db_url_export} && exec celery -A app.worker.celery_app beat --loglevel INFO"
      ]
      environment = local.backend_common_environment
      secrets     = local.backend_common_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = local.log_group_beat
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "beat"
        }
      }
    }
  ])

  tags = var.tags
}

# One-off migration task: NOT run as a service. Invoke it as a pre-deploy step
# (see README "Deploying a new release") via:
#   aws ecs run-task --cluster <cluster> --task-definition <this family> \
#     --launch-type FARGATE --network-configuration '...'
# Kept separate from the api service startup so N concurrently-scaling api
# tasks never race each other running `alembic upgrade head` at once.
resource "aws_ecs_task_definition" "migrate" {
  family                   = "${var.name_prefix}-migrate"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "migrate"
      image     = var.image_api
      essential = true
      command = [
        "sh", "-c",
        "${local.db_url_export} && exec alembic upgrade head"
      ]
      environment = local.backend_common_environment
      secrets     = local.backend_common_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = local.log_group_migrate
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "migrate"
        }
      }
    }
  ])

  tags = var.tags
}

# --- ECS services ---

resource "aws_ecs_service" "web" {
  name            = "${var.name_prefix}-web"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = var.web_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.app_security_group_id]
    assign_public_ip = var.assign_public_ip
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 3000
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 60

  lifecycle {
    ignore_changes = [desired_count]
  }

  depends_on = [aws_lb_listener.https]
  tags       = var.tags
}

resource "aws_ecs_service" "api" {
  name            = "${var.name_prefix}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.app_security_group_id]
    assign_public_ip = var.assign_public_ip
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 60

  lifecycle {
    ignore_changes = [desired_count]
  }

  depends_on = [aws_lb_listener.https]
  tags       = var.tags
}

resource "aws_ecs_service" "worker" {
  name            = "${var.name_prefix}-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.app_security_group_id]
    assign_public_ip = var.assign_public_ip
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  lifecycle {
    ignore_changes = [desired_count]
  }

  tags = var.tags
}

# Beat is a fixed singleton: exactly one scheduler must ever run, or reminder
# leads would double-fire. No autoscaling target is created for it, and
# desired_count is a hardcoded 1, not a variable.
resource "aws_ecs_service" "beat" {
  name            = "${var.name_prefix}-beat"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.beat.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.app_security_group_id]
    assign_public_ip = var.assign_public_ip
  }

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  tags = var.tags
}

# --- Autoscaling: web, api, worker only. Beat intentionally excluded. ---

resource "aws_appautoscaling_target" "web" {
  max_capacity       = var.web_autoscaling_max
  min_capacity       = var.web_autoscaling_min
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.web.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "web_cpu" {
  name               = "${var.name_prefix}-web-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.web.resource_id
  scalable_dimension = aws_appautoscaling_target.web.scalable_dimension
  service_namespace  = aws_appautoscaling_target.web.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = var.autoscaling_cpu_target_percent
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
  }
}

resource "aws_appautoscaling_target" "api" {
  max_capacity       = var.api_autoscaling_max
  min_capacity       = var.api_autoscaling_min
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${var.name_prefix}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = var.autoscaling_cpu_target_percent
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
  }
}

resource "aws_appautoscaling_target" "worker" {
  max_capacity       = var.worker_autoscaling_max
  min_capacity       = var.worker_autoscaling_min
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "worker_cpu" {
  name               = "${var.name_prefix}-worker-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = var.autoscaling_cpu_target_percent
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
  }
}
