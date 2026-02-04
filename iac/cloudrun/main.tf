terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "5.20.0"
    }
  }
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "asia-east1"
}

variable "service_name" {
  type = string
}

variable "image" {
  type = string
}

variable "min_instances" {
  type    = number
  default = 0
}

variable "max_instances" {
  type    = number
  default = 2
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_cloud_run_v2_service" "backend" {
  name     = var.service_name
  location = var.region

  template {
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.image

      ports {
        container_port = 8000
      }

      env {
        name  = "PORT"
        value = "8000"
      }
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}
