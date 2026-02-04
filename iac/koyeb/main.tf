terraform {
  required_version = ">= 1.3.0"
  required_providers {
    koyeb = {
      source  = "koyeb/koyeb"
      version = "0.6.0"
    }
  }
}

variable "koyeb_token" {
  type      = string
  sensitive = true
}

variable "app_name" {
  type = string
}

variable "service_name" {
  type = string
}

variable "repo_url" {
  type = string
}

variable "branch" {
  type    = string
  default = "main"
}

variable "region" {
  type    = string
  default = "fra"
}

variable "instance_type" {
  type    = string
  default = "free"
}

variable "port" {
  type    = number
  default = 8000
}

provider "koyeb" {
  token = var.koyeb_token
}

resource "koyeb_app" "backend" {
  name = var.app_name
}

resource "koyeb_service" "backend" {
  app_name = koyeb_app.backend.name

  definition {
    name = var.service_name

    instance_types {
      type = var.instance_type
    }

    ports {
      port     = var.port
      protocol = "http"
    }

    routes {
      path = "/"
      port = var.port
    }

    regions = [var.region]

    scalings {
      min = 1
      max = 1
    }

    env {
      key   = "PORT"
      value = tostring(var.port)
    }

    git {
      repository = var.repo_url
      branch     = var.branch
      workdir    = "backend"
      builder    = "docker"
      dockerfile = "backend/Dockerfile"
    }
  }
}
