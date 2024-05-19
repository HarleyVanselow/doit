locals {
  source_files = ["../main.py", "../requirements.txt"]
}

data "template_file" "t_file" {
  count = length(local.source_files)

  template = file(element(local.source_files, count.index))
}
resource "local_file" "to_temp_dir" {
  count    = length(local.source_files)
  filename = "${path.module}/temp/${basename(element(local.source_files, count.index))}"
  content  = element(data.template_file.t_file.*.rendered, count.index)
}

data "archive_file" "archive" {
  type        = "zip"
  output_path = "${path.module}/${var.name}.zip"
  source_dir  = "${path.module}/temp"

  depends_on = [
    local_file.to_temp_dir
  ]
}
variable "name" {
  default = "doit"
}