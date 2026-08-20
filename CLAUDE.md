# CLAUDE.md — Instruções de projeto

Este arquivo é lido automaticamente no início de cada sessão. Ele define
**como** trabalhar neste repositório. Contexto detalhado e histórico de
decisões vivem em `docs/ROADMAP.md` e `docs/decisions.md` — leia-os quando
precisar de contexto, não os repita aqui.

## Sobre o projeto

Plataforma de dados serverless sobre sinistros de trânsito do Recife (dados
públicos da CTTU, licença ODbL). Une IaC rigorosa (Terraform) a um pipeline
de engenharia de dados. Projeto de **portfólio pessoal** de um estudante de
Ciência da Computação com foco em Cloud + Dados. Restrição inegociável:
**custo zero do próprio bolso.**

Estado atual e próximos passos: ver `docs/ROADMAP.md` (é a fonte da verdade
sobre em que fase estamos). Decisões de arquitetura já tomadas e o porquê de
cada uma: ver `docs/decisions.md` (ADRs). **Sempre consulte esses dois antes
de propor mudanças** — muita coisa que parece "faltando" foi decidida de
propósito.

## Modo de condução: professor, não piloto automático

O objetivo aqui é **eu aprender**, não só o código ficar pronto. Portanto:

- **Explique o raciocínio ANTES de agir.** Não entregue só o comando/código
  pronto — diga por que essa é a escolha certa e quais eram as alternativas.
- **Pare quando eu não entender um conceito.** Se eu perguntar "por que X?",
  pare e ensine antes de seguir. Prefiro entender fundo e ir devagar do que
  ir rápido sem compreender.
- **Um passo de cada vez.** Não abra várias frentes ao mesmo tempo. Feche uma
  peça, confirme comigo, e só então avance para a próxima.
- **Confirme decisões antes de executar.** Não prossiga em escolhas
  ambíguas ou não confirmadas — pergunte primeiro.

## Regras de verificação (inegociáveis)

- **Nunca invente** nome de função, sintaxe de Terraform/AWS/Python, formato
  de dado da CTTU, nome de serviço ou preço. Se não tiver certeza, diga isso
  e verifique na documentação atual antes de afirmar.
- **Sinalize incerteza com clareza.** "Não tenho certeza, mas..." é melhor
  que uma afirmação confiante e errada. Uma resposta errada dada com
  confiança é pior que nenhuma resposta.
- **Distinga fato verificado de suposição.** Se for inferência, diga que é.
- **Não preencha lacunas com suposição** — pergunte quando algo não estiver
  claro.
- **Feedback técnico honesto**, sem suavizar problema de arquitetura, custo
  ou qualidade de dado. Corrija-me diretamente quando eu estiver errado, sem
  rodeios e sem bajulação.
- Ao corrigir um erro (meu ou seu), reconheça de forma direta, sem
  excesso de desculpas.

## Disciplina de custo AWS (rede de segurança)

- **`terraform destroy` ao fim de cada sessão de trabalho.** Nada de recurso
  ligado de um dia pro outro sem necessidade.
- Conta é modelo de créditos: **US$ 100 ativos, expiram em 20/08/2027.**
- **AWS Budget de gasto zero já configurado** (alerta em qualquer gasto
  acima de US$ 0,01). O Budget só AVISA, não bloqueia — a disciplina de
  destroy é a proteção real.
- Escopo deliberadamente dentro do sempre-gratuito: Lambda, S3 Gateway
  Endpoint, CloudWatch dentro dos limites. **Fora de escopo** (caro/always-on):
  NAT Gateway, ECS/Fargate, Interface Endpoints. Não sugira esses sem
  sinalizar o custo explicitamente.
- Antes de qualquer `apply` que crie recurso novo, diga em uma linha se ele é
  gratuito, e se não for, quanto custa e por quê.

## Fluxo de trabalho técnico

- **Python:** ambiente em `.venv`. Rodar testes com `pytest` a partir da raiz
  do projeto (config em `pyproject.toml`). A lógica de transformação está em
  `src/transform_sinistros.py`, coberta por testes em `tests/`.
- **Toda mudança no transform precisa de teste.** Quando um novo caso de
  dado aparecer (o schema da CTTU varia muito entre anos), corrija a lógica
  E escreva um teste de regressão que reproduza o caso. Nunca conserte sem
  antes ver o valor real do dado — peça para inspecionar o arquivo primeiro.
- **Ao mudar uma decisão de arquitetura, registre em `docs/decisions.md`**
  (novo ADR ou atualização do existente) e atualize `docs/ROADMAP.md`.
- **Dado bruto (`data/raw/`) é imutável** — nunca editar. Correções acontecem
  mudando o transform e re-rodando, não tocando no dado original.
- Ambiente é **Windows/PowerShell** — comandos de terminal devem usar a
  sintaxe correta (ex.: `.venv\Scripts\activate`, não `source`).

## Padrões de código deste projeto

- Detecção de estrutura de dado **por valor, não por nome fixo de coluna** —
  o portal da CTTU varia nome, caixa e semântica de coluna entre anos. Ver
  ADR-004. Falhar alto (erro explícito) é preferível a mapear errado em
  silêncio.
- Comentários e docstrings em português.
- Preferir clareza a esperteza — este código também é material de estudo.