terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }

  # GCS remote state — the bucket must exist before running 'terraform init'.
  # Create it once manually:
  #   gcloud storage buckets create gs://traveltime-465606-terraform-state \
  #     --project=traveltime-465606 \
  #     --location=australia-southeast1 \
  #     --uniform-bucket-level-access
  backend "gcs" {
    bucket = "traveltime-465606-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project               = var.project_id
  region                = var.region
  billing_project       = var.project_id
  user_project_override = true
}

# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

data "google_project" "project" {
  project_id = var.project_id
}

# ---------------------------------------------------------------------------
# Budget alert
#
# Sends email at 50 %, 80 %, and 100 % of the AUD $20 monthly ceiling for
# both actual and forecasted spend.  The notification channel is wired up via
# Cloud Monitoring; the billing console also shows the alert.
# ---------------------------------------------------------------------------

resource "google_monitoring_notification_channel" "budget_email" {
  project      = var.project_id
  display_name = "Budget Alert — ${var.alert_email}"
  type         = "email"

  labels = {
    email_address = var.alert_email
  }

  force_delete = false

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_billing_budget" "monthly_budget" {
  billing_account = var.billing_account_id
  display_name    = "genai-supply-chain — AUD ${var.budget_amount_aud}/mo"

  budget_filter {
    projects               = ["projects/${data.google_project.project.number}"]
    credit_types_treatment = "INCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = "AUD"
      # units is a string in the Billing Budget API
      units = tostring(floor(var.budget_amount_aud))
    }
  }

  # Actual spend thresholds
  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }
  threshold_rules {
    threshold_percent = 0.8
    spend_basis       = "CURRENT_SPEND"
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }

  # Forecasted spend thresholds
  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "FORECASTED_SPEND"
  }
  threshold_rules {
    threshold_percent = 0.8
    spend_basis       = "FORECASTED_SPEND"
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = [
      google_monitoring_notification_channel.budget_email.id,
    ]
    # Also delivers alerts to billing admins via the default billing IAM roles
    disable_default_iam_recipients = false
  }
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "project_number" {
  description = "Numeric project ID — referenced by billing budget filter"
  value       = data.google_project.project.number
}

output "budget_name" {
  description = "Full resource name of the billing budget"
  value       = google_billing_budget.monthly_budget.name
}

output "notification_channel_id" {
  description = "Cloud Monitoring notification channel used for budget emails"
  value       = google_monitoring_notification_channel.budget_email.id
}
