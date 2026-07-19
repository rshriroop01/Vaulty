variable "name_prefix" {
  description = "Prefix applied to all secret names in this module (e.g. \"vaultly/staging\")."
  type        = string
}

variable "secret_keys" {
  description = <<-EOT
    Logical names of app secrets to provision shells for (e.g. ["secret-key",
    "anthropic-api-key", "stripe-secret-key", "stripe-webhook-secret",
    "s3-access-key", "s3-secret-key"]). Each becomes a Secrets Manager secret
    at "<name_prefix>/<key>" with NO value set by Terraform — populate the
    actual value out-of-band (console, CLI, or CI/CD secret injection) after
    apply. Terraform only owns the resource shell (name/ARN/rotation config),
    never the plaintext.
  EOT
  type        = list(string)
  default = [
    "secret-key",            # app SECRET_KEY (JWT signing)
    "anthropic-api-key",     # ANTHROPIC_API_KEY
    "stripe-secret-key",     # STRIPE_SECRET_KEY
    "stripe-webhook-secret", # STRIPE_WEBHOOK_SECRET
    "stripe-price-premium",  # STRIPE_PRICE_PREMIUM
    "stripe-price-family",   # STRIPE_PRICE_FAMILY
    "s3-access-key",         # S3_ACCESS_KEY — IAM user key, see README (task role is preferred but app code requires explicit creds)
    "s3-secret-key",         # S3_SECRET_KEY
    "smtp-username",         # SES SMTP username — not wired into a task def yet; app has no SMTP auth support (see README known gap)
    "smtp-password",         # SES SMTP password
  ]
}

variable "recovery_window_days" {
  description = "Days Secrets Manager retains a deleted secret before permanent removal (0 = immediate delete, useful for staging churn)."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags to merge onto every resource in this module."
  type        = map(string)
  default     = {}
}
