terraform {
  # use_lockfile (lock nativo do S3) é GA a partir do 1.11 — ver ADR-011.
  # Abaixo disso o argumento é experimental e não deve ser usado.
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # NÃO existe bloco "backend" aqui — e isso é deliberado, é o coração do
  # bootstrap (ADR-011).
  #
  # Este diretório CRIA o bucket que servirá de backend para terraform/main/.
  # Se ele declarasse um backend S3, dependeria de um bucket que ainda não
  # existe: o problema do ovo e da galinha.
  #
  # Sem bloco backend, o Terraform usa o padrão — um arquivo terraform.tfstate
  # local, neste diretório. Ele é a "chave que fica do lado de fora do cofre".
}

provider "aws" {
  region = var.regiao

  # Aplicadas automaticamente a todo recurso deste diretório.
  default_tags {
    tags = {
      Projeto  = "recife-sinistros"
      Estagio  = "bootstrap"
      Gerencia = "terraform"
      Duravel  = "true" # sobrevive ao destroy de cada sessão — não apagar
    }
  }
}
