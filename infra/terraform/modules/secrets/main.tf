# Secrets Manager resource shells only. Terraform creates the named secret
# container (and controls its lifecycle/tags), but never writes a value into
# it — that happens out-of-band (console, `aws secretsmanager put-secret-value`,
# or a CI/CD deploy step with access to the real credential). This keeps
# secret plaintext out of .tf files, plan output, and state for these entries.
#
# NOTE: the RDS master password is handled separately by the database module
# via `manage_master_user_password`, which is fully AWS-managed and doesn't
# need a shell here.

resource "aws_secretsmanager_secret" "app" {
  for_each = toset(var.secret_keys)

  name                    = "${var.name_prefix}/${each.key}"
  description             = "Vaultly app secret: ${each.key}. Value injected out-of-band, not by Terraform."
  recovery_window_in_days = var.recovery_window_days

  tags = merge(var.tags, {
    Name = "${var.name_prefix}/${each.key}"
  })

  lifecycle {
    # Never let a `terraform apply` clobber a value that was injected
    # out-of-band into the secret's version.
    ignore_changes = [tags["LastRotated"]]
  }
}
