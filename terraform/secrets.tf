# ---------------------------------------------------------------------------
# Secret Manager — CDSE credentials for satellite imagery download
#
# Secret VALUES are set out-of-band via gcloud (not in Terraform state) to
# prevent credentials from appearing in plan output or state files.
# Only the secret resource shells and IAM bindings are managed here.
# ---------------------------------------------------------------------------

resource "google_project_service" "secretmanager" {
  project                    = var.project_id
  service                    = "secretmanager.googleapis.com"
  disable_on_destroy         = false
  disable_dependent_services = false
}

resource "google_secret_manager_secret" "cdse_username" {
  project   = var.project_id
  secret_id = "cdse-username"

  replication {
    auto {}
  }

  labels = {
    project    = var.project_id
    managed_by = "terraform"
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "cdse_password" {
  project   = var.project_id
  secret_id = "cdse-password"

  replication {
    auto {}
  }

  labels = {
    project    = var.project_id
    managed_by = "terraform"
  }

  depends_on = [google_project_service.secretmanager]
}

# Allow the Cloud Run Job's identity to read both secrets at runtime.
resource "google_project_iam_member" "runner_secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.pipeline_runner.email}"
}
