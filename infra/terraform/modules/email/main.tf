# SES domain identity + DKIM (Easy DKIM) + optional custom MAIL FROM + DMARC.
# Assumes var.route53_zone_id points at an already-existing hosted zone for
# var.domain — this module only adds records into it, it does not create zones.

resource "aws_ses_domain_identity" "this" {
  domain = var.domain
}

resource "aws_route53_record" "ses_verification" {
  zone_id = var.route53_zone_id
  name    = "_amazonses.${var.domain}"
  type    = "TXT"
  ttl     = 600
  records = [aws_ses_domain_identity.this.verification_token]
}

resource "aws_ses_domain_identity_verification" "this" {
  domain     = aws_ses_domain_identity.this.id
  depends_on = [aws_route53_record.ses_verification]
}

resource "aws_ses_domain_dkim" "this" {
  domain = aws_ses_domain_identity.this.domain
}

resource "aws_route53_record" "dkim" {
  count   = 3
  zone_id = var.route53_zone_id
  name    = "${aws_ses_domain_dkim.this.dkim_tokens[count.index]}._domainkey.${var.domain}"
  type    = "CNAME"
  ttl     = 600
  records = ["${aws_ses_domain_dkim.this.dkim_tokens[count.index]}.dkim.amazonses.com"]
}

# --- Custom MAIL FROM domain (SPF alignment) ---

resource "aws_ses_domain_mail_from" "this" {
  count            = var.mail_from_subdomain != "" ? 1 : 0
  domain           = aws_ses_domain_identity.this.domain
  mail_from_domain = "${var.mail_from_subdomain}.${var.domain}"
}

resource "aws_route53_record" "mail_from_mx" {
  count   = var.mail_from_subdomain != "" ? 1 : 0
  zone_id = var.route53_zone_id
  name    = aws_ses_domain_mail_from.this[0].mail_from_domain
  type    = "MX"
  ttl     = 600
  records = ["10 feedback-smtp.${data.aws_region.current.name}.amazonses.com"]
}

resource "aws_route53_record" "mail_from_spf" {
  count   = var.mail_from_subdomain != "" ? 1 : 0
  zone_id = var.route53_zone_id
  name    = aws_ses_domain_mail_from.this[0].mail_from_domain
  type    = "TXT"
  ttl     = 600
  records = ["v=spf1 include:amazonses.com -all"]
}

data "aws_region" "current" {}

# --- DMARC ---

resource "aws_route53_record" "dmarc" {
  count   = var.create_dmarc_record ? 1 : 0
  zone_id = var.route53_zone_id
  name    = "_dmarc.${var.domain}"
  type    = "TXT"
  ttl     = 600
  records = [
    join("; ", compact([
      "v=DMARC1",
      "p=${var.dmarc_policy}",
      var.dmarc_report_email != "" ? "rua=mailto:${var.dmarc_report_email}" : "",
    ]))
  ]
}
