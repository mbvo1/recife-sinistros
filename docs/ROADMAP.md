ROADMAP — Plataforma Serverless de Sinistros (CTTU/Recife)

Este é o mapa do projeto: as fases, em ordem de dependência, e onde estamos. Atualizar conforme avançamos. As fases são um guia, não um contrato — ajustamos no caminho.

Onde o projeto mora
Sua máquina — repositório Git, editado no VSCode. É a fonte da verdade.
GitHub (mbvo1) — para onde você dá push.
AWS — onde a infraestrutura sobe via Terraform (fases 2+).
Restrição inegociável

Custo zero do próprio bolso. Arquitetura desenhada dentro de camadas sempre-gratuitas. terraform destroy após cada sessão. AWS Budgets com alarme de gasto baixo antes de subir qualquer coisa.

Fases
Fase 0 — Fundações locais (sem AWS, custo zero) ✅ CONCLUÍDA
 Definir schema canônico (silver) a partir do dado real
 Escrever a transformação bronze→silver (src/transform_sinistros.py)
 Suíte de testes local (tests/, 18 testes passando)
 Estrutura do repositório
 Baixar os 10 anos (2015–2024) e colocar em data/raw/
 Rodar o transform nos 10 anos e conferir as métricas de cada um — todos os 10 anos passam sem erro.

Achados da varredura completa (2015–2024):

A coluna de severidade mudou de nome duas vezes: natureza (2015) → natureza_acidente (2016–2021) → natureza de novo (2022–2024). A detecção por valor (não por nome fixo) absorveu a reversão sem precisar de ajuste — validação de que essa foi a estratégia certa.
2020 tem volume bem menor (4.092 linhas) que os anos vizinhos. Hipótese não confirmada: efeito da pandemia no trânsito. Investigar na Fase 6 se relevante para a análise.
Todos os anos de 2016 em diante têm vitimasfatais; só 2015 não tem.
Fase 1 — Verificar a conta AWS ✅ CONCLUÍDA
 Confirmar modelo da conta: legado vs. créditos → modelo de créditos (conta criada em 20/08/2026, após a mudança de jul/2025)
 Confirmar saldo de créditos e data de expiração → US$ 100,00 ativos, US$ 0,00 usados, expira em 20/08/2027
 Configurar AWS Budgets com alarme de gasto baixo → orçamento de gasto zero criado, alerta em qualquer gasto acima de US$ 0,01

Nota: a suposição inicial de "créditos expiram em 6 meses" (citada nas conversas anteriores) não se confirmou — a conta real mostra expiração em 1 ano. Não sabemos por que a suposição inicial divergiu (pode ter mudado, ou variar por conta/promoção) — o que vale é o que a própria conta mostra.

Fase 2 — IaC base (Terraform) ← ESTAMOS AQUI

Ordem decidida por dependência (ver ADR-010) e backend por bootstrap (ADR-011).

 Estágio 0 — bootstrap do backend (state local): cria só o bucket de state, com versionamento (ADR-012). Lock resolvido: nativo do S3 via use_lockfile, sem DynamoDB (ADR-011, atualização de 21/08/2026) — exige Terraform >= 1.11. Esta infra é durável (sobrevive ao destroy).
 Config principal usa o bucket acima como backend remoto.
 Buckets S3 bronze/silver (base — não dependem de nada)
 VPC + subnet privada + S3 Gateway Endpoint
 IAM least-privilege (depois dos buckets — políticas referenciam os ARNs)
 CloudWatch (log group; destino das métricas do transform)
 Disciplina plan → apply → destroy (miolo é efêmero; backend permanece)
Fase 3 — Lambda
 src/handler.py envolvendo o transform
 Empacotamento (resolver limite de tamanho — decidir ZIP vs container)
 Gatilho de evento S3 (PUT no bronze dispara a Lambda)
Fase 4 — Ingestão
 scripts/ingest.py: baixa CSVs pela API do CKAN, sobe no bronze
 Rodar os 10 anos pelo pipeline real na nuvem (2ª validação, agora em AWS)
Fase 5 — CI/CD
 GitHub Actions: terraform validate + plan
 Checkov validando segurança antes de aplicar
Fase 6 — Análise (o payoff de "dados")
 Consultar o silver
 Agregação por bairro (sem geocoding — ver decisão ADR-008)
Fase 7 — Polimento de portfólio
 README com diagrama de arquitetura
 ADRs revisados (docs/decisions.md)
 Nota explícita: VPC incluída por portfólio (ADR-001)
 Atribuição ODbL
Pendências conhecidas (não esquecer)
Granularidade de tipo_sinistro: 2024 é fino, 2015 é grosso. Se quiser comparar espécie entre anos, precisa de uma tabela de-para. Em aberto.
vitimas cru: o dicionário oficial contradiz o dado de 2015; não derivamos "total de vítimas". Ver ADR-007.
Anos 2016–2023: transform não testado neles ainda (Fase 0).
Papel no Projeto 5e6 (CESAR): se/como este projeto absorve a camada de deploy AWS daquela disciplina — ainda em aberto.