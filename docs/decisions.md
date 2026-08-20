Decisões de Arquitetura (ADRs)

Registro curto das decisões e do porquê. A intenção é que qualquer pessoa (inclusive você daqui a três meses) entenda as escolhas sem arqueologia.

ADR-001 — VPC incluída por portfólio, não por necessidade funcional

Uma Lambda que só lê e escreve no S3 não precisa de VPC — o acesso ao S3 acontece pela rede da própria AWS. A VPC (com subnet privada, Gateway Endpoint e IAM na fronteira) foi incluída deliberadamente para demonstrar competência de rede, que é o que uma vaga de Cloud avalia. Decisão consciente, documentada para deixar claro que entendemos quando a VPC é necessária e quando é escolha.

ADR-002 — S3 Gateway Endpoint em vez de NAT Gateway

Dado que há um recurso dentro da VPC (a Lambda, ver ADR-001) que precisa alcançar o S3, usamos um Gateway Endpoint (grátis, ilimitado para S3/ DynamoDB) e não um NAT Gateway (cobrado por hora + por GB). Mantém o custo zero. Consequência: a Lambda na VPC não tem saída para a internet — aceitável, porque ela só fala com o S3.

ADR-003 — Schema canônico "opção A" + vitimasfatais

O silver projeta para um conjunto fixo de ~19 conceitos comuns aos anos, mais vitimasfatais. Motivo de incluir vitimasfatais mesmo sendo só de 2019+: severidade é o sinal central de um projeto de trânsito, e lidar com evolução de schema (campo que nasce no meio da série, com nulo honesto para anos antigos) é competência a demonstrar. Nulo para anos sem a coluna — nunca zero.

ADR-004 — Detecção de severidade por VALOR (swap tipo/natureza + rename)

As colunas tipo e natureza trocaram de significado entre 2015 (tipo=severidade, natureza=espécie) e 2024 (invertido). Como não sabemos em que ano exato o swap ocorreu, o transform detecta qual coluna é severidade inspecionando os valores (subconjunto de {SEM VÍTIMA, COM VÍTIMA, VÍTIMA FATAL}), não pelo nome nem pelo ano. Falha alto (erro explícito) se nenhuma coluna bater.

Atualização (achado ao rodar 2016 real): 2016 usa o mesmo layout semântico de 2015 (espécie em tipo), mas a coluna de severidade se chama natureza_acidente, não natureza — um terceiro nome de coluna para o mesmo conceito. A detecção foi generalizada para considerar tipo, natureza e natureza_acidente como candidatas. Além disso, 2016 tem 147 linhas com severidade vazia — tratado como dado ausente legítimo (conta na métrica severidade_vazia_no_silver), não como erro que quebra o pipeline.

Atualização (achado ao rodar 2018 real): a coluna de data aparece como DATA (maiúscula) em 2018, não data. Corrigido normalizando TODOS os nomes de coluna para minúsculas logo na leitura do CSV (_detecta_coluna_* e o resto do pipeline continuam usando nomes minúsculos). Padrão geral: o portal varia nome e caixa de coluna entre anos.

Atualização (achado ao rodar 2019 real): a coluna natureza_acidente tinha 2 linhas (de ~12.000) com valores "ENTRADA E SAÍDA" e "APOIO" — ruído pontual, provavelmente vazado de outro campo administrativo. A checagem original exigia que todos os valores únicos fossem válidos, o que quebrava com qualquer contaminação, por menor que fosse. Trocado para um limiar de proporção de linhas (LIMIAR_SEVERIDADE_VALIDA = 0.95): a coluna é aceita se ≥95% das linhas preenchidas baterem com SEVERIDADE_VALIDAS, e as linhas fora do padrão são contadas na métrica severidade_ruido_no_bruto em vez de quebrar o pipeline ou serem escondidas. Ressalva: 95% foi escolhido por julgamento (bem acima do ruído real de ~0,02% em 2019, bem abaixo do ponto onde eu confiaria numa coluna errada) — não é um valor derivado estatisticamente. Se anos futuros tiverem mais ruído legítimo, revisar o limiar.

ADR-005 — Filtro de qualidade: só situacao == FINALIZADA

situacao é o status do chamado, não do acidente. CANCELADA, DUPLICIDADE, EM ATENDIMENTO, PENDENTE e EM ABERTO não são acidentes confirmados. O silver mantém só FINALIZADA. O bronze preserva tudo (filtro é não-destrutivo). O número de descartados vira métrica de CloudWatch e é documentado (em 2015, ~29%).

ADR-006 — Vazio em contagem → 0, mas nunca em vitimasfatais

Célula vazia numa contagem de veículo (moto, auto, ...) é interpretada como 0 ("tipo não envolvido"), com base no padrão de preenchimento observado (muitos vazios, quase nenhum "0" explícito). É inferência, documentada. NÃO se aplica a vitimasfatais: ali, ausência é NULO, porque houve mortes em anos sem a coluna e afirmar 0 seria fabricar dado.

ADR-007 — vitimas mantido cru; sem "total de vítimas" derivado

O dicionário oficial afirma que antes de 2017 vitimas inclui os fatais. O dado de 2015 desmente: as 24 linhas fatais têm vitimas=0. Como a regra do dicionário não se confirma, não derivamos um "total de vítimas" — seria apoiar num número que o dado não sustenta. vitimas fica cru, com a ressalva registrada.

ADR-008 — Análise agregada por bairro (sem geocoding)

Os CSVs não têm latitude/longitude — só localização em texto (bairro, endereço). Mapa de pontos exigiria geocoding (custo, rate limit — fura o custo zero). A análise mira agregação por bairro (campo categórico limpo após normalização). Decisão de escopo consciente.

ADR-009 — O dicionário oficial está desatualizado; o dado real é a verdade

O JSON de metadados do portal só documenta o layout de ~2015, ignora as 18 colunas novas de 2024, lista IDs de recurso antigos e diverge da página do dataset na frequência de atualização (JSON diz "trimestral", página diz "semestral"). Tratamos o dado real como fonte de verdade e o dicionário como referência a ser verificada, não confiada cegamente.

ADR-010 — Ordem de construção da Fase 2 (por dependência)

A ordem do Terraform decorre da cadeia de dependência entre recursos, não de preferência: buckets S3 → VPC/subnet/Gateway Endpoint → IAM → CloudWatch, e depois Lambda (Fase 3). Justificativa:

Buckets não dependem de nada e são referenciados por todo o resto → base.
VPC/Endpoint dependem só de si mesmos.
IAM referencia os ARNs dos buckets nas políticas least-privilege → só pode vir depois dos buckets existirem.
CloudWatch (log group) é quase independente; destino das métricas do transform.
Lambda amarra tudo (role IAM + VPC + buckets + CloudWatch) → por último.

Nota de custo: nesta arquitetura, nada tem cobrança por hora quando ocioso (S3 = por GB armazenado ~centavos; Lambda = por invocação; VPC/subnet/ Endpoint/IAM = grátis). O terraform destroy por sessão é mais disciplina/ higiene e demonstração de portfólio do que necessidade de custo — mas permanece obrigatório pelos três motivos (hábito profissional, portfólio, proteção contra recurso caro adicionado por engano).

ADR-011 — State remoto via bootstrap em dois estágios

Escolhido state remoto (S3 + lock) em vez de state local, apesar de o projeto ser solo (backend remoto existe para evitar conflito de state entre membros de um time — necessidade funcional ausente aqui). Motivo: é portfólio — igual à VPC (ADR-001), a demonstração é o ponto, não a necessidade.

O bucket de state precisa existir antes do Terraform poder usá-lo como backend (problema "ovo e galinha"). Resolvido em dois estágios: uma config Terraform pequena, com state local, cria só o bucket+lock; a config principal usa esse bucket como backend remoto. Consequência prática: o backend de state é infra durável e grátis (poucos KB + requisições de lock) que SOBREVIVE ao terraform destroy de cada sessão; todo o resto (buckets de dado, VPC, Lambda) é infra efêmera, destruída e recriada a cada sessão.

A verificar na implementação (NÃO presumir): o mecanismo de lock. O padrão clássico é DynamoDB, mas o Terraform introduziu lock nativo via S3 (sem DynamoDB) em versão recente. Confirmar na documentação atual qual é o recomendado hoje antes de escrever o backend.