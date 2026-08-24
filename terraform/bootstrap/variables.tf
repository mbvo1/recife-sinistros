variable "regiao" {
  description = "Região AWS onde o bucket de state será criado."
  type        = string
  default     = "us-east-1"
}

variable "nome_bucket_state" {
  description = <<-EOT
    Nome do bucket de state.

    Nome de bucket S3 é GLOBALMENTE único — em toda a AWS, todas as contas do
    mundo, não só na sua. Daí o sufixo aleatório. Se o apply falhar com
    "BucketAlreadyExists", significa que outra conta pegou este nome: troque
    o sufixo e rode de novo.

    Optamos por um sufixo fixo, e não por random_id, porque este bucket nasce
    uma vez na vida e o nome é colado à mão no backend do terraform/main/ —
    previsibilidade vale mais que elegância aqui (ADR-011).
  EOT
  type        = string
  default     = "recife-sinistros-tfstate-3kg23f"
}
