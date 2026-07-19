variable "domain" {
  description = "Domain to verify as an SES identity (e.g. \"vaultly.app\" or \"staging.vaultly.app\")."
  type        = string
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID for var.domain, used to create the SES verification TXT record and the 3 DKIM CNAME records. Assumes the zone already exists (not created by this module)."
  type        = string
}

variable "mail_from_subdomain" {
  description = "Subdomain used as the custom MAIL FROM domain (e.g. \"mail\" -> mail.vaultly.app), improving deliverability/SPF alignment. Set to \"\" to skip custom MAIL FROM setup."
  type        = string
  default     = "mail"
}

variable "create_dmarc_record" {
  description = "Whether to create a basic DMARC policy record (_dmarc.<domain>)."
  type        = bool
  default     = true
}

variable "dmarc_policy" {
  description = "DMARC policy value (p=none|quarantine|reject). Start at none, tighten after monitoring reports."
  type        = string
  default     = "none"
}

variable "dmarc_report_email" {
  description = "Email address to receive DMARC aggregate reports. Leave empty to omit the rua tag."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to merge onto every resource in this module."
  type        = map(string)
  default     = {}
}
