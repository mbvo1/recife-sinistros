# Plataforma Serverless de Sinistros de Trânsito — Recife (CTTU)

> **Status: em construção (Fase 0 de 7).** Este README descreve o estado real
> do projeto, sem inflar o que ainda não existe. Ver `docs/ROADMAP.md`.

Plataforma de dados *serverless* sobre sinistros (acidentes) de trânsito do
Recife, unindo infraestrutura como código (IaC) rigorosa a um pipeline de
engenharia de dados. Projeto de portfólio pessoal.

## O que já existe (Fase 0)

- Transformação **bronze→silver** dos dados anuais da CTTU, em Python puro
  (`src/transform_sinistros.py`), com schema canônico que harmoniza a evolução
  do dado entre 2015 e 2024.
- Suíte de testes local (`tests/`) — 13 testes, sem dependência dos CSVs reais.

## O que ainda NÃO existe

Toda a camada de nuvem (VPC, S3, Lambda, IAM, CloudWatch), o Terraform, a
ingestão via API do CKAN e o CI. Ver `docs/ROADMAP.md` para as fases.

## Arquitetura pretendida

```
Upload/ingestão de dado bruto (CTTU)
        │
        ▼
   S3 (raw/bronze) ──evento de PUT──► Lambda (validação/transformação)
        │                                      │
        ▼                                      ▼
   VPC (subnet privada) ◄─ S3 Gateway Endpoint    S3 (curated/silver)
        │
        ▼
   CloudWatch (logs, métricas, alarme de erro/custo)

Provisionado via Terraform (state em S3 + lock DynamoDB),
com CI via GitHub Actions + Checkov.
```

Nota de projeto: a Lambda é colocada dentro da VPC **por decisão de portfólio**,
não por necessidade funcional. Ver `docs/decisions.md` (ADR-001).

## Estrutura

```
src/    transformação (e, em fases futuras, o handler da Lambda)
tests/  testes locais (pytest)
docs/   ROADMAP e decisões de arquitetura (ADRs)
data/   dados brutos locais (não versionados)
```

## Como rodar localmente

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Rodar os testes:
pytest -v

# Rodar a transformação nos dados (após colocar CSVs em data/raw/):
python src/transform_sinistros.py
```

## Dados e licença

Fonte: **Portal de Dados Abertos do Recife** (`dados.recife.pe.gov.br`),
dataset publicado pela **CTTU**. Dados sob **Open Database License (ODbL)**.
Ver `data/README.md` para como obter os arquivos.
