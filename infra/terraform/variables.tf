variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "service_name" {
  type    = string
  default = "portfolio-chat-agent"
}

variable "chat_image" {
  type        = string
  description = "Container image for the chat agent"
}

variable "openai_api_key" {
  type      = string
  sensitive = true
}

variable "llm_provider" {
  type    = string
  default = "openai"
}

variable "intent_provider" {
  type    = string
  default = ""
}

variable "planner_provider" {
  type    = string
  default = ""
}

variable "synth_provider" {
  type    = string
  default = ""
}

variable "codegen_provider" {
  type    = string
  default = ""
}

variable "openai_model" {
  type    = string
  default = "gpt-4o-mini"
}

variable "intent_model" {
  type    = string
  default = "gpt-4o-mini"
}

variable "planner_model" {
  type    = string
  default = "gpt-4o-mini"
}

variable "codegen_model" {
  type    = string
  default = "gpt-4o-mini"
}

variable "synth_model" {
  type    = string
  default = "gpt-4o-mini"
}

variable "vertexai_project" {
  type    = string
  default = ""
}

variable "vertexai_location" {
  type    = string
  default = ""
}

variable "non_finance_nudge" {
  type    = string
  default = "What are my top 5 stocks?"
}

variable "portfolio_api_url" {
  type = string
}

variable "portfolio_api_token" {
  type      = string
  sensitive = true
  default   = ""
}

variable "search_provider" {
  type    = string
  default = "stub"
}

variable "search_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "search_api_url" {
  type    = string
  default = ""
}

variable "search_top_k" {
  type    = number
  default = 5
}

variable "langfuse_public_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "langfuse_secret_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "langfuse_host" {
  type    = string
  default = "https://cloud.langfuse.com"
}

variable "checkpointer_dsn" {
  type      = string
  sensitive = true
  default   = ""
}

variable "allow_unauthenticated" {
  type    = bool
  default = true
}

variable "cloudsql_instance_connection_name" {
  type    = string
  default = ""
}

variable "cloudsql_project_id" {
  type    = string
  default = ""
}
