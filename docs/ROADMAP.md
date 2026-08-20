# ROADMAP — Plataforma Serverless de Sinistros (CTTU/Recife)

Este é o mapa do projeto: as fases, em ordem de dependência, e onde estamos.
Atualizar conforme avançamos. As fases são um guia, não um contrato — ajustamos
no caminho.

## Onde o projeto mora

- **Sua máquina** — repositório Git, editado no VSCode. É a fonte da verdade.
- **GitHub (`mbvo1`)** — para onde você dá `push`.
- **AWS** — onde a infraestrutura sobe via Terraform (fases 2+).

## Restrição inegociável

Custo zero do próprio bolso. Arquitetura desenhada dentro de camadas
sempre-gratuitas. `terraform destroy` após cada sessão. AWS Budgets com alarme
de gasto baixo **antes** de subir qualquer coisa.

---

## Fases

### Fase 0 — Fundações locais (sem AWS, custo zero) ← ESTAMOS AQUI
- [x] Definir schema canônico (silver) a partir do dado real
- [x] Escrever a transformação bronze→silver (`src/transform_sinistros.py`)
- [x] Suíte de testes local (`tests/`, 13 testes passando)
- [x] Estrutura do repositório
- [ ] Baixar os 10 anos (2015–2024) e colocar em `data/raw/`
- [ ] Rodar o transform nos 10 anos e conferir as métricas de cada um
      (é aqui que os anos do meio, ainda não testados, são validados)

### Fase 1 — Verificar a conta AWS (só você faz) — BLOQUEADOR das fases de nuvem
- [ ] Confirmar modelo da conta: legado (Free Tier 12 meses) vs. créditos
- [ ] Confirmar saldo de créditos e data de expiração
- [ ] Configurar **AWS Budgets** com alarme de gasto baixo (ex.: US$ 1–5)

### Fase 2 — IaC base (Terraform)
- [ ] Backend: state em S3 + lock em DynamoDB
- [ ] Buckets bronze/silver
- [ ] IAM least-privilege
- [ ] VPC + subnet privada + S3 Gateway Endpoint
- [ ] CloudWatch (log group, métricas)
- [ ] Disciplina plan → apply → destroy

### Fase 3 — Lambda
- [ ] `src/handler.py` envolvendo o transform
- [ ] Empacotamento (resolver limite de tamanho — decidir ZIP vs container)
- [ ] Gatilho de evento S3 (PUT no bronze dispara a Lambda)

### Fase 4 — Ingestão
- [ ] `scripts/ingest.py`: baixa CSVs pela **API do CKAN**, sobe no bronze
- [ ] Rodar os 10 anos pelo pipeline real na nuvem (2ª validação, agora em AWS)

### Fase 5 — CI/CD
- [ ] GitHub Actions: `terraform validate` + `plan`
- [ ] Checkov validando segurança antes de aplicar

### Fase 6 — Análise (o payoff de "dados")
- [ ] Consultar o silver
- [ ] Agregação por bairro (sem geocoding — ver decisão ADR-008)

### Fase 7 — Polimento de portfólio
- [ ] README com diagrama de arquitetura
- [ ] ADRs revisados (`docs/decisions.md`)
- [ ] Nota explícita: VPC incluída por portfólio (ADR-001)
- [ ] Atribuição ODbL

---

## Pendências conhecidas (não esquecer)

- **Granularidade de `tipo_sinistro`**: 2024 é fino, 2015 é grosso. Se quiser
  comparar espécie entre anos, precisa de uma tabela de-para. Em aberto.
- **`vitimas` cru**: o dicionário oficial contradiz o dado de 2015; não
  derivamos "total de vítimas". Ver ADR-007.
- **Anos 2016–2023**: transform não testado neles ainda (Fase 0).
- **Papel no Projeto 5e6 (CESAR)**: se/como este projeto absorve a camada de
  deploy AWS daquela disciplina — ainda em aberto.
