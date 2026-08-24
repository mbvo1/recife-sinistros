# ---------------------------------------------------------------------------
# Estágio 0 — bootstrap do backend de state (ADR-011)
#
# Cria a ÚNICA infraestrutura durável do projeto: o bucket que guarda o state
# de todo o resto. Roda uma vez, no início do projeto, e permanece.
#
# Tudo aqui é gratuito. O S3 cobra por GB armazenado (aqui, alguns KB) e por
# requisição (um punhado por sessão) — fração de centavo, abaixo do
# arredondamento da fatura. Nada tem cobrança por hora.
#
# O lock NÃO aparece como recurso: é o lock nativo do S3, ativado por
# use_lockfile no backend do terraform/main/. Não há tabela DynamoDB.
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "state" {
  bucket = var.nome_bucket_state

  # Guarda-corpo. O Terraform recusa qualquer plano que destrua este bucket,
  # e falha alto em vez de obedecer.
  #
  # A rotina do projeto é rodar destroy ao fim de cada sessão (ADR-011). Isto
  # existe para o dia em que o destroy for disparado no diretório errado —
  # destruir este bucket apagaria o registro de toda a infraestrutura.
  #
  # Para remover de verdade (só se estiver encerrando o projeto): apague este
  # bloco lifecycle primeiro, depois rode o destroy.
  lifecycle {
    prevent_destroy = true
  }
}

# ADR-012 — versionamento.
#
# Lock e versionamento resolvem problemas DIFERENTES: o lock impede que dois
# applies escrevam ao mesmo tempo; o versionamento permite voltar atrás quando
# o state é corrompido, truncado ou apagado. Um não substitui o outro.
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Criptografia em repouso.
#
# Na prática é redundante: desde jan/2023 a AWS aplica SSE-S3 por padrão em
# todo bucket novo. Declarada explicitamente por dois motivos — deixa a
# intenção legível no código, e o Checkov (previsto na Fase 5) sinaliza
# bucket sem criptografia explícita.
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # SSE-S3: gerenciado pela AWS, sem custo
    }
  }
}

# O arquivo de state contém, em texto claro, tudo que o Terraform sabe sobre
# a infraestrutura — incluindo qualquer valor sensível que um recurso exponha.
# Este bucket não pode ser público em nenhuma circunstância.
resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
