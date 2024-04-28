terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "5.26.0"
    }
  }
  backend "gcs" {
    bucket = "moviebot-code-storage"
    prefix = "terraform/state"
  }
}
provider "google" {
  project = "promising-silo-421623"
  region  = "us-east1"
}
variable "OMDB_API_KEY" {}

resource "google_cloudfunctions2_function" "moviebot" {
  name        = "moviebot"
  description = "My function"
  location    = "us-east1"

  build_config {
    runtime     = "python312"
    entry_point = "hello_http" # Set the entry point 
    environment_variables = {
      "OMDB_API_KEY" : var.OMDB_API_KEY
    }
    source {
      storage_source {
        bucket = google_storage_bucket.bucket.name
        object = google_storage_bucket_object.archive.name
      }
    }
  }
}
resource "google_storage_bucket" "bucket" {
  name     = "moviebot-code-storage"
  location = "US"
}

resource "google_storage_bucket_object" "archive" {
  name   = "${timestamp()}.zip"
  bucket = google_storage_bucket.bucket.name
  source = data.archive_file.archive.output_path
}

resource "google_cloud_run_service_iam_binding" "binding" {
  location = google_cloudfunctions2_function.moviebot.location
  project  = google_cloudfunctions2_function.moviebot.project
  service  = google_cloudfunctions2_function.moviebot.name
  role     = "roles/run.invoker"
  members = [
    "allUsers"
  ]
}

resource "google_firestore_database" "database" {
  name        = "(default)"
  location_id = "nam5"
  type        = "FIRESTORE_NATIVE"
}
