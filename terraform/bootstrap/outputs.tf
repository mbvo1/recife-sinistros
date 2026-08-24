output "nome_bucket_state" {
  description = "Nome do bucket de state criado."
  value       = aws_s3_bucket.state.id
}

output "regiao" {
  description = "Região onde o bucket vive."
  value       = var.regiao
}

# Conveniência: imprime o bloco pronto para colar no terraform/main/.
# Evita erro de digitação no nome do bucket — que renderia um "bucket não
# encontrado" no init, confuso de diagnosticar.
output "bloco_backend_para_o_main" {
  description = "Cole este bloco no versions.tf do terraform/main/."
  value       = <<-EOT

    terraform {
      backend "s3" {
        bucket       = "${aws_s3_bucket.state.id}"
        key          = "main/terraform.tfstate"
        region       = "${var.regiao}"
        encrypt      = true
        use_lockfile = true # lock nativo do S3 — sem DynamoDB (ADR-011)
      }
    }
  EOT
}
