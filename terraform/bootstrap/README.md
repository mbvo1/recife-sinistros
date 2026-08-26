# Estágio 0 — bootstrap do backend de state

Este diretório cria **a única infraestrutura durável do projeto**: o bucket S3
que guarda o state de todo o resto.

Contexto e justificativa: ADR-011 e ADR-012 em `docs/decisions.md`.

## ⚠️ NÃO rode `terraform destroy` aqui

A rotina do projeto é `terraform destroy` ao fim de cada sessão — mas isso vale
para `terraform/main/`, **nunca para este diretório**.

Destruir este bucket apaga o registro de toda a infraestrutura do projeto. O
recurso tem `prevent_destroy = true`, então o Terraform recusa o plano e falha
alto. O guarda-corpo existe justamente para o dia em que o `destroy` for
disparado no diretório errado.

## Por que este diretório existe (o ovo e a galinha)

Queremos o state no S3. Para usar S3 como backend, o bloco `backend` precisa
apontar para um bucket **que já exista** quando o `init` roda. Mas quem cria o
bucket é o Terraform — e essa config precisaria guardar o state em algum lugar,
que seria o bucket que ainda não existe. Circular.

A saída: este diretório **não declara backend nenhum**. Sem bloco `backend`, o
Terraform usa o padrão — `terraform.tfstate` local, aqui mesmo. Como ele não
depende de bucket algum, pode rodar antes de qualquer bucket existir.

É a chave que fica do lado de fora do cofre.

## O que é criado

Todos gratuitos. O S3 cobra por GB armazenado (aqui, alguns KB) e por
requisição (um punhado por sessão). Nada tem cobrança por hora.

| Recurso | Para quê |
|---|---|
| `aws_s3_bucket` | O bucket de state |
| `aws_s3_bucket_versioning` | ADR-012 — recuperar state corrompido |
| `aws_s3_bucket_server_side_encryption_configuration` | Criptografia em repouso, explícita |
| `aws_s3_bucket_public_access_block` | Bloqueia exposição pública |

Note que **não há tabela DynamoDB**. O lock é o nativo do S3, ativado por
`use_lockfile = true` no backend do `terraform/main/` — é configuração, não
infraestrutura (ADR-011).

## Como rodar (uma vez na vida do projeto)

```powershell
cd terraform\bootstrap
terraform init
terraform plan      # confira: 4 recursos a criar, nenhum a destruir
terraform apply
```

O `apply` imprime o output `bloco_backend_para_o_main`: o bloco `backend`
pronto para colar no `versions.tf` do `terraform/main/`. Use o output em vez de
digitar o nome do bucket à mão — erro de digitação ali vira um "bucket não
encontrado" no `init`, chato de diagnosticar.

Para ver os outputs de novo depois:

```powershell
terraform output
```

## Se o `apply` falhar com `BucketAlreadyExists`

Nome de bucket S3 é globalmente único, em toda a AWS. Alguém pegou o nome
antes. Troque o sufixo em `variables.tf` (`nome_bucket_state`) e rode de novo.

## Recuperação: o state local sumiu

O `terraform.tfstate` deste diretório **não é versionado** — `*.tfstate` está no
`.gitignore` do projeto, e é assim que queremos: state em repositório é hábito
ruim de carregar, e num repositório público de portfólio parece descuido.

A consequência aceita: se sua máquina morrer ou o arquivo for apagado, o
Terraform perde o vínculo com o bucket. O bucket continua lá; só o registro
sumiu. Como este diretório rastreia poucos recursos, recuperar é rápido.

Com o bucket ainda existindo na AWS, rode daqui:

```powershell
terraform init
terraform import aws_s3_bucket.state                                    recife-sinistros-tfstate-3kg23f
terraform import aws_s3_bucket_versioning.state                         recife-sinistros-tfstate-3kg23f
terraform import aws_s3_bucket_server_side_encryption_configuration.state recife-sinistros-tfstate-3kg23f
terraform import aws_s3_bucket_public_access_block.state                recife-sinistros-tfstate-3kg23f
terraform plan   # deve dizer "No changes" — se disser, a recuperação deu certo
```

Os quatro usam o **nome do bucket** como ID de import (verificado na doc do
provider em 26/08/2026). Se o nome do bucket tiver mudado, ajuste.

O `terraform plan` no fim é a validação: se ele reportar mudanças, algo divergiu
entre o código e o que existe na AWS — investigue antes de aplicar.

> Alternativa: o Terraform 1.12+ aceita blocos `import` declarativos com o
> atributo `identity`, o que é mais moderno que os comandos acima. Para uma
> recuperação pontual, os comandos são mais diretos.
