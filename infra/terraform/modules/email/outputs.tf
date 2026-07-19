output "domain_identity_arn" {
  description = "ARN of the SES domain identity (use for scoping ses:SendEmail IAM policy)."
  value       = aws_ses_domain_identity.this.arn
}

output "verified_domain" {
  description = "The verified sending domain."
  value       = aws_ses_domain_identity.this.domain
}

output "dkim_tokens" {
  description = "DKIM tokens published as CNAME records."
  value       = aws_ses_domain_dkim.this.dkim_tokens
}

output "mail_from_domain" {
  description = "Custom MAIL FROM domain, if configured."
  value       = var.mail_from_subdomain != "" ? aws_ses_domain_mail_from.this[0].mail_from_domain : null
}
