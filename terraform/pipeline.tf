# ---------------------------------------------------------------------------
# API enablement
# ---------------------------------------------------------------------------

resource "google_project_service" "run" {
  project                    = var.project_id
  service                    = "run.googleapis.com"
  disable_on_destroy         = false
  disable_dependent_services = false
}

resource "google_project_service" "artifactregistry" {
  project                    = var.project_id
  service                    = "artifactregistry.googleapis.com"
  disable_on_destroy         = false
  disable_dependent_services = false
}

resource "google_project_service" "cloudbuild" {
  project                    = var.project_id
  service                    = "cloudbuild.googleapis.com"
  disable_on_destroy         = false
  disable_dependent_services = false
}

resource "google_project_service" "cloudscheduler" {
  project                    = var.project_id
  service                    = "cloudscheduler.googleapis.com"
  disable_on_destroy         = false
  disable_dependent_services = false
}

# ---------------------------------------------------------------------------
# Imagery cache bucket
# ---------------------------------------------------------------------------

resource "google_storage_bucket" "imagery" {
  name          = var.imagery_bucket_name
  project       = var.project_id
  location      = var.region
  force_destroy = false

  # Automatically delete imagery older than 90 days to contain storage costs.
  lifecycle_rule {
    condition { age = 90 }
    action { type = "Delete" }
  }

  uniform_bucket_level_access = true

  labels = {
    project    = var.project_id
    managed_by = "terraform"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# ---------------------------------------------------------------------------
# Artifact Registry
# ---------------------------------------------------------------------------

resource "google_artifact_registry_repository" "pipeline" {
  project       = var.project_id
  location      = var.region
  repository_id = "supply-chain-pipeline"
  format        = "DOCKER"
  description   = "Container images for the daily supply-chain vision pipeline"

  labels = {
    project    = var.project_id
    managed_by = "terraform"
  }

  depends_on = [google_project_service.artifactregistry]
}

# ---------------------------------------------------------------------------
# Service accounts
# ---------------------------------------------------------------------------

resource "google_service_account" "pipeline_runner" {
  project      = var.project_id
  account_id   = "pipeline-runner"
  display_name = "Supply Chain Pipeline — Cloud Run Job identity"
  description  = "Used by the Cloud Run Job to access Firestore, GCS, and Vertex AI"
}

resource "google_service_account" "pipeline_scheduler" {
  project      = var.project_id
  account_id   = "pipeline-scheduler"
  display_name = "Supply Chain Pipeline — Cloud Scheduler identity"
  description  = "Minimum-privilege SA: only allowed to create executions of the pipeline job"
}

# ---------------------------------------------------------------------------
# IAM — pipeline_runner (least-privilege, scoped to specific resources)
# ---------------------------------------------------------------------------

# Firestore read/write (watchlist_items reads + daily_briefings writes).
resource "google_project_iam_member" "runner_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.pipeline_runner.email}"
}

# Vertex AI inference for Gemini 2.5 Flash calls via google-genai SDK.
resource "google_project_iam_member" "runner_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.pipeline_runner.email}"
}

# GCS read/write scoped to the imagery bucket only (not project-wide).
resource "google_storage_bucket_iam_member" "runner_gcs" {
  bucket = google_storage_bucket.imagery.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline_runner.email}"
}

# Dashboard imagery is served directly to browsers from storage.googleapis.com.
resource "google_storage_bucket_iam_member" "imagery_public_read" {
  bucket = google_storage_bucket.imagery.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# ---------------------------------------------------------------------------
# IAM — Cloud Build service account → Artifact Registry push
# Cloud Build's default SA must be able to push the built image.
# ---------------------------------------------------------------------------

resource "google_artifact_registry_repository_iam_member" "cloudbuild_writer" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.pipeline.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"

  depends_on = [google_project_service.cloudbuild]
}

# ---------------------------------------------------------------------------
# Container image build + push via Cloud Build
#
# Rebuilds whenever any source file or the Dockerfile changes (SHA256 trigger).
# Uses gcloud builds submit with cloudbuild.yaml at the project root so that
# the full repo is the build context and backend/Dockerfile can reference it.
# ---------------------------------------------------------------------------

locals {
  image_url = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.pipeline.repository_id}/backend:latest"
}

resource "null_resource" "build_push_image" {
  triggers = {
    dockerfile_hash      = filesha256("${path.module}/../backend/Dockerfile")
    requirements_hash    = filesha256("${path.module}/../backend/requirements.txt")
    cloudbuild_hash      = filesha256("${path.module}/../cloudbuild.yaml")
    main_hash            = filesha256("${path.module}/../backend/src/main.py")
    analyser_hash        = filesha256("${path.module}/../backend/src/analyser.py")
    image_processor_hash = filesha256("${path.module}/../backend/src/image_processor.py")
    stac_client_hash     = filesha256("${path.module}/../backend/src/stac_client.py")
    geometry_utils_hash  = filesha256("${path.module}/../backend/src/geometry_utils.py")
    models_hash          = filesha256("${path.module}/../backend/src/models.py")
  }

  provisioner "local-exec" {
    command = <<-EOT
      ~/google-cloud-sdk/bin/gcloud builds submit "${path.module}/.." \
        --project="${var.project_id}" \
        --config="${path.module}/../cloudbuild.yaml" \
        --substitutions="_IMAGE=${local.image_url}" \
        --suppress-logs
    EOT
  }

  depends_on = [
    google_artifact_registry_repository.pipeline,
    google_artifact_registry_repository_iam_member.cloudbuild_writer,
    google_project_service.cloudbuild,
    google_project_service.artifactregistry,
  ]
}

# ---------------------------------------------------------------------------
# Cloud Run Job
#
# CPU 2 / Memory 4Gi — for a 5-minute daily run this consumes ~18 000 vCPU-s
# and ~36 000 GiB-s per month, well within the 180 000 / 360 000 free-tier
# limits.  Timeout is generous (1 h) to handle large watchlists gracefully.
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_job" "pipeline" {
  name     = "supply-chain-pipeline"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        image = local.image_url

        env {
          name  = "GCS_BUCKET_NAME"
          value = google_storage_bucket.imagery.name
        }
        # Suppress ADC "no project ID" warning; also used by google-cloud libs.
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }

        # CDSE credentials injected from Secret Manager at runtime.
        env {
          name = "CDSE_USERNAME"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.cdse_username.secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "CDSE_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.cdse_password.secret_id
              version = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
        }
      }

      timeout         = "3600s"
      max_retries     = 1
      service_account = google_service_account.pipeline_runner.email
    }
  }

  labels = {
    project     = var.project_id
    environment = "production"
    managed_by  = "terraform"
  }

  depends_on = [
    null_resource.build_push_image,
    google_project_service.run,
    google_secret_manager_secret.cdse_username,
    google_secret_manager_secret.cdse_password,
    google_project_iam_member.runner_secretmanager,
  ]
}

# ---------------------------------------------------------------------------
# IAM — Cloud Scheduler → Cloud Run Job (invoke only, no broader Run access)
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.pipeline.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pipeline_scheduler.email}"
}

# ---------------------------------------------------------------------------
# Cloud Scheduler — daily trigger
#
# Calls the Cloud Run Jobs v1 execute endpoint with an OIDC token issued to
# pipeline-scheduler.  The audience matches the regional Run hostname so the
# token is accepted without extra configuration.
# ---------------------------------------------------------------------------

resource "google_cloud_scheduler_job" "daily_pipeline" {
  name      = "daily-supply-chain-pipeline"
  schedule  = var.scheduler_cron
  time_zone = "UTC"
  region    = var.region
  project   = var.project_id

  http_target {
    uri = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.pipeline.name}:run"

    http_method = "POST"
    body        = base64encode("{}")

    oidc_token {
      service_account_email = google_service_account.pipeline_scheduler.email
      audience              = "https://${var.region}-run.googleapis.com/"
    }
  }

  depends_on = [
    google_cloud_run_v2_job_iam_member.scheduler_invoker,
    google_project_service.cloudscheduler,
    google_project_service.run,
  ]
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "cloud_run_job_name" {
  description = "Name of the Cloud Run Job"
  value       = google_cloud_run_v2_job.pipeline.name
}

output "imagery_bucket_url" {
  description = "GCS bucket storing the processed imagery JPEG cache"
  value       = google_storage_bucket.imagery.url
}

output "artifact_registry_repo" {
  description = "Artifact Registry repository hosting the pipeline container"
  value       = google_artifact_registry_repository.pipeline.name
}

output "pipeline_image_url" {
  description = "Full Artifact Registry image URL used by the Cloud Run Job"
  value       = local.image_url
}

output "scheduler_job_name" {
  description = "Cloud Scheduler job that triggers the daily pipeline run"
  value       = google_cloud_scheduler_job.daily_pipeline.name
}
