# Decisões de Arquitetura (ADRs)

Registro curto das decisões e do porquê. A intenção é que qualquer pessoa
(inclusive você daqui a três meses) entenda as escolhas sem arqueologia.

---

## ADR-001 — VPC incluída por portfólio, não por necessidade funcional
Uma Lambda que só lê e escreve no S3 **não precisa** de VPC — o acesso ao S3
acontece pela rede da própria AWS. A VPC (com subnet privada, Gateway Endpoint
e IAM na fronteira) foi incluída **deliberadamente para demonstrar competência
de rede**, que é o que uma vaga de Cloud avalia. Decisão consciente, documentada
para deixar claro que entendemos quando a VPC é necessária e quando é escolha.

## ADR-002 — S3 Gateway Endpoint em vez de NAT Gateway
Dado que há um recurso dentro da VPC (a Lambda, ver ADR-001) que precisa
alcançar o S3, usamos um **Gateway Endpoint** (grátis, ilimitado para S3/
DynamoDB) e não um **NAT Gateway** (cobrado por hora + por GB). Mantém o custo
zero. Consequência: a Lambda na VPC não tem saída para a internet — aceitável,
porque ela só fala com o S3.

## ADR-003 — Schema canônico "opção A" + `vitimasfatais`
O silver projeta para um conjunto fixo de ~19 conceitos comuns aos anos, mais
`vitimasfatais`. Motivo de incluir `vitimasfatais` mesmo sendo só de 2019+:
severidade é o sinal central de um projeto de trânsito, e lidar com evolução de
schema (campo que nasce no meio da série, com nulo honesto para anos antigos) é
competência a demonstrar. Nulo para anos sem a coluna — **nunca** zero.

## ADR-004 — Detecção de severidade por VALOR (swap tipo/natureza)
As colunas `tipo` e `natureza` **trocaram de significado** entre 2015
(`tipo`=severidade, `natureza`=espécie) e 2024 (invertido). Como não sabemos em
que ano exato o swap ocorreu e temos poucos anos em mãos, o transform detecta
qual coluna é severidade **inspecionando os valores** (subconjunto de
{SEM VÍTIMA, COM VÍTIMA, VÍTIMA FATAL}), não pelo nome nem pelo ano. Falha alto
(erro explícito) se nenhuma coluna bater.

## ADR-005 — Filtro de qualidade: só `situacao == FINALIZADA`
`situacao` é o status do chamado, não do acidente. CANCELADA, DUPLICIDADE,
EM ATENDIMENTO, PENDENTE e EM ABERTO não são acidentes confirmados. O silver
mantém só FINALIZADA. O bronze preserva tudo (filtro é não-destrutivo). O número
de descartados vira métrica de CloudWatch e é documentado (em 2015, ~29%).

## ADR-006 — Vazio em contagem → 0, mas nunca em `vitimasfatais`
Célula vazia numa contagem de veículo (`moto`, `auto`, ...) é interpretada como
0 ("tipo não envolvido"), com base no padrão de preenchimento observado (muitos
vazios, quase nenhum "0" explícito). É **inferência**, documentada. NÃO se
aplica a `vitimasfatais`: ali, ausência é NULO, porque houve mortes em anos sem
a coluna e afirmar 0 seria fabricar dado.

## ADR-007 — `vitimas` mantido cru; sem "total de vítimas" derivado
O dicionário oficial afirma que antes de 2017 `vitimas` inclui os fatais. O dado
de 2015 desmente: as 24 linhas fatais têm `vitimas`=0. Como a regra do
dicionário não se confirma, **não derivamos** um "total de vítimas" — seria
apoiar num número que o dado não sustenta. `vitimas` fica cru, com a ressalva
registrada.

## ADR-008 — Análise agregada por bairro (sem geocoding)
Os CSVs **não têm** latitude/longitude — só localização em texto (bairro,
endereço). Mapa de pontos exigiria geocoding (custo, rate limit — fura o custo
zero). A análise mira **agregação por `bairro`** (campo categórico limpo após
normalização). Decisão de escopo consciente.

## ADR-009 — O dicionário oficial está desatualizado; o dado real é a verdade
O JSON de metadados do portal só documenta o layout de ~2015, ignora as 18
colunas novas de 2024, lista IDs de recurso antigos e diverge da página do
dataset na frequência de atualização (JSON diz "trimestral", página diz
"semestral"). Tratamos o **dado real** como fonte de verdade e o dicionário como
referência a ser verificada, não confiada cegamente.
