resource "google_project_service" "required" {
  for_each = toset([
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "artifactregistry.googleapis.com",
  ])

  service                    = each.value
  disable_on_destroy          = false
  disable_dependent_services  = false
}

resource "google_service_account" "chat_service" {
  account_id   = "chat-agent-sa"
  display_name = "Portfolio Chat Agent Service Account"
}

resource "google_project_iam_member" "chat_service_vertex_access" {
  project = var.project_id
  role   = "roles/aiplatform.user"
  member = "serviceAccount:${google_service_account.chat_service.email}"
}

resource "google_project_iam_member" "chat_service_cloudsql_access" {
  count   = var.cloudsql_instance_connection_name != "" ? 1 : 0
  project = var.cloudsql_project_id != "" ? var.cloudsql_project_id : var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.chat_service.email}"
}

resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "openai-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "openai_api_key" {
  secret      = google_secret_manager_secret.openai_api_key.id
  secret_data = var.openai_api_key
}

resource "google_secret_manager_secret_iam_member" "openai_api_key_access" {
  secret_id = google_secret_manager_secret.openai_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.chat_service.email}"
}

resource "google_secret_manager_secret" "checkpointer_dsn" {
  count     = var.checkpointer_dsn != "" ? 1 : 0
  secret_id = "chat-checkpointer-dsn"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "checkpointer_dsn" {
  count       = var.checkpointer_dsn != "" ? 1 : 0
  secret      = google_secret_manager_secret.checkpointer_dsn[0].id
  secret_data = var.checkpointer_dsn
}

resource "google_secret_manager_secret_iam_member" "checkpointer_dsn_access" {
  count     = var.checkpointer_dsn != "" ? 1 : 0
  secret_id = google_secret_manager_secret.checkpointer_dsn[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.chat_service.email}"
}

resource "google_cloud_run_v2_service" "chat_service" {
  name     = var.service_name
  location = var.region

  template {
    annotations = var.cloudsql_instance_connection_name != "" ? {
      "run.googleapis.com/cloudsql-instances" = var.cloudsql_instance_connection_name
    } : {}
    service_account = google_service_account.chat_service.email

    containers {
      image = var.chat_image

      env {
        name = "OPENAI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.openai_api_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }

      env {
        name  = "INTENT_PROVIDER"
        value = var.intent_provider
      }

      env {
        name  = "PLANNER_PROVIDER"
        value = var.planner_provider
      }

      env {
        name  = "SYNTH_PROVIDER"
        value = var.synth_provider
      }

      env {
        name  = "CODEGEN_PROVIDER"
        value = var.codegen_provider
      }

      env {
        name  = "OPENAI_MODEL"
        value = var.openai_model
      }

      env {
        name  = "INTENT_MODEL"
        value = var.intent_model
      }

      env {
        name  = "PLANNER_MODEL"
        value = var.planner_model
      }

      env {
        name  = "CODEGEN_MODEL"
        value = var.codegen_model
      }

      env {
        name  = "SYNTH_MODEL"
        value = var.synth_model
      }

      env {
        name  = "VERTEXAI_PROJECT"
        value = var.vertexai_project
      }

      env {
        name  = "VERTEXAI_LOCATION"
        value = var.vertexai_location
      }

      env {
        name  = "NON_FINANCE_NUDGE"
        value = var.non_finance_nudge
      }

      env {
        name  = "PORTFOLIO_API_URL"
        value = var.portfolio_api_url
      }

      env {
        name  = "PORTFOLIO_API_TOKEN"
        value = var.portfolio_api_token
      }

      env {
        name  = "SEARCH_PROVIDER"
        value = var.search_provider
      }

      env {
        name  = "SEARCH_API_KEY"
        value = var.search_api_key
      }

      env {
        name  = "SEARCH_API_URL"
        value = var.search_api_url
      }

      env {
        name  = "SEARCH_TOP_K"
        value = tostring(var.search_top_k)
      }

      env {
        name  = "LANGFUSE_PUBLIC_KEY"
        value = var.langfuse_public_key
      }

      env {
        name  = "LANGFUSE_SECRET_KEY"
        value = var.langfuse_secret_key
      }

      env {
        name  = "LANGFUSE_HOST"
        value = var.langfuse_host
      }

      dynamic "env" {
        for_each = var.checkpointer_dsn != "" ? [1] : []
        content {
          name = "CHECKPOINTER_DB_DSN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.checkpointer_dsn[0].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count    = var.allow_unauthenticated ? 1 : 0
  location = google_cloud_run_v2_service.chat_service.location
  name     = google_cloud_run_v2_service.chat_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
