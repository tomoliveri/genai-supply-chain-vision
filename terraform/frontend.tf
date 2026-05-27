locals {
  frontend_image_url = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.pipeline.repository_id}/frontend:latest"
}

# ---------------------------------------------------------------------------
# Build and push the frontend image whenever source changes
# ---------------------------------------------------------------------------

resource "null_resource" "build_push_frontend" {
  triggers = {
    dockerfile_hash     = filesha256("${path.module}/../frontend/Dockerfile")
    next_config_hash    = filesha256("${path.module}/../frontend/next.config.ts")
    package_json_hash   = filesha256("${path.module}/../frontend/package.json")
    env_production_hash = filesha256("${path.module}/../frontend/.env.production")
    gcloudignore_hash   = filesha256("${path.module}/../frontend/.gcloudignore")
    src_hash = sha256(join("", [
      for f in sort(fileset("${path.module}/../frontend/src", "**/*.{ts,tsx,css}")) :
      filesha256("${path.module}/../frontend/src/${f}")
    ]))
  }

  provisioner "local-exec" {
    command = <<-EOT
      ~/google-cloud-sdk/bin/gcloud builds submit "${path.module}/../frontend" \
        --project="${var.project_id}" \
        --tag="${local.frontend_image_url}" \
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
# Cloud Run service — public, no auth required
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "frontend" {
  name     = "supplywatch-dashboard"
  location = var.region
  project  = var.project_id

  ingress = "INGRESS_TRAFFIC_ALL"

  labels = {
    project     = var.project_id
    environment = "production"
    managed_by  = "terraform"
  }

  template {
    service_account = google_service_account.frontend_runner.email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = local.frontend_image_url

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "NODE_ENV"
        value = "production"
      }
    }
  }

  depends_on = [null_resource.build_push_frontend]
}

# Allow unauthenticated public access
resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Minimal service account for the frontend container
resource "google_service_account" "frontend_runner" {
  project      = var.project_id
  account_id   = "frontend-runner"
  display_name = "SupplyWatch Dashboard — Cloud Run identity"
  description  = "No GCP permissions needed; Firebase is accessed directly from the browser."
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "dashboard_url" {
  description = "Public URL of the SupplyWatch dashboard"
  value       = google_cloud_run_v2_service.frontend.uri
}
