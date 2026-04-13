output "service_url" {
  value = google_cloud_run_v2_service.chat_service.uri
}

output "service_account" {
  value = google_service_account.chat_service.email
}

output "openai_secret" {
  value = google_secret_manager_secret.openai_api_key.id
}
