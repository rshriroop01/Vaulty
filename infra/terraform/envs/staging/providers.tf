provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      project    = "vaultly"
      env        = var.environment
      managed-by = "terraform"
    }
  }
}
