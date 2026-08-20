# data/

Os dados brutos **não** são versionados (ver `.gitignore`) — são baixáveis do
Portal de Dados Abertos do Recife e ficam grandes. Guarde-os localmente aqui.

## Onde colocar

Baixe os CSVs anuais (2015–2024) do dataset "Chamados de Sinistros (Acidentes)
de Trânsito com e sem vítimas" e coloque em `data/raw/`. O script de
transformação procura por qualquer arquivo `*<ano>*.csv` nesta pasta.

Portal: https://dados.recife.pe.gov.br  (dataset publicado pela CTTU)

> Atenção: os IDs de recurso do portal mudam. Baixe sempre pela página do
> dataset, não por URLs de download antigas (elas retornam 404).
