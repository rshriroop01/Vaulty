variable "bucket_name" {
  description = "Globally-unique name for the documents bucket (e.g. \"vaultly-documents-staging\")."
  type        = string
}

variable "noncurrent_version_expiration_days" {
  description = "Days to retain noncurrent object versions before they're permanently expired. Versioning is on so a bad overwrite/delete is recoverable within this window."
  type        = number
  default     = 90
}

variable "noncurrent_version_transition_days" {
  description = "Days before noncurrent versions transition to STANDARD_IA to cut storage cost while still recoverable."
  type        = number
  default     = 30
}

variable "abort_incomplete_multipart_upload_days" {
  description = "Days after which incomplete multipart uploads (abandoned presigned uploads) are aborted and cleaned up."
  type        = number
  default     = 7
}

variable "cors_allowed_origins" {
  description = "Origins allowed to perform presigned direct-to-S3 browser uploads (the web app's URL(s))."
  type        = list(string)
}

variable "tags" {
  description = "Additional tags to merge onto every resource in this module."
  type        = map(string)
  default     = {}
}
