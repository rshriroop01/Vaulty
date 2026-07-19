terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Partial backend config: bucket/key/region/dynamodb_table are supplied at
  # `terraform init -backend-config=backend.hcl` time so this file never
  # hardcodes a bucket that may not exist yet. See ../../README.md.
  backend "s3" {
    key     = "vaultly/prod/terraform.tfstate"
    encrypt = true
  }
}
