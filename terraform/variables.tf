variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "traveltime-465606"
}

variable "region" {
  description = "Default GCP region for resources"
  type        = string
  default     = "australia-southeast1"
}

variable "billing_account_id" {
  description = "GCP billing account ID (without 'billingAccounts/' prefix) — set in terraform.tfvars"
  type        = string
}

variable "budget_amount_aud" {
  description = "Monthly budget ceiling in AUD"
  type        = number
  default     = 20
}

variable "alert_email" {
  description = "Email address to receive budget alert notifications — set in terraform.tfvars"
  type        = string
}

variable "state_bucket" {
  description = "GCS bucket name used for Terraform remote state (must exist before terraform init)"
  type        = string
  default     = "traveltime-465606-terraform-state"
}

variable "imagery_bucket_name" {
  description = "GCS bucket name for the processed imagery JPEG cache"
  type        = string
  default     = "traveltime-465606-imagery-cache"
}

variable "scheduler_cron" {
  description = "UTC cron expression for the daily pipeline trigger (2am UTC = noon AEST)"
  type        = string
  default     = "0 2 * * *"
}
