output "bucket_id" {
  description = "S3 bucket name."
  value       = aws_s3_bucket.documents.id
}

output "bucket_arn" {
  description = "S3 bucket ARN (use for IAM policy scoping)."
  value       = aws_s3_bucket.documents.arn
}

output "bucket_regional_domain_name" {
  description = "Regional domain name of the bucket."
  value       = aws_s3_bucket.documents.bucket_regional_domain_name
}
