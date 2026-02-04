terraform {
  required_version = ">= 1.3.0"
  required_providers {
    render = {
      source  = "render-oss/render"
      version = "1.6.0"
    }
  }
}

variable "render_api_key" {
  type      = string
  sensitive = true
}

variable "render_owner_id" {
  type = string
}

variable "repo_url" {
  type = string
}

variable "branch" {
  type    = string
  default = "main"
}

variable "service_name" {
  type = string
}

variable "region" {
  type    = string
  default = "oregon"
}

provider "render" {
  api_key  = var.render_api_key
  owner_id = var.render_owner_id
}

resource "render_web_service" "backend" {
  name             = var.service_name
  plan             = "free"
  region           = var.region
  health_check_path = "/health/full"

  runtime_source = {
    native_runtime = {
      auto_deploy   = false
      repo_url      = var.repo_url
      branch        = var.branch
      build_command = "pip install -r backend/requirements.txt"
      start_command = "uvicorn backend.main:app --host 0.0.0.0 --port 8000"
    }
  }
}
