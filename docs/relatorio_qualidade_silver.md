# Relatório de qualidade — camada silver

Gerado por `src/transform_sinistros.py` a partir dos CSVs de `data/raw/`. Ver `docs/decisions.md` (ADR-005, ADR-014, ADR-015) para o porquê de cada métrica.

- Descartadas e duplicados somam com as linhas silver: entrada = silver + descartadas + duplicados.
- "vitimasfatais preenchida" = % de linhas do silver com a célula preenchida; "n/a" = coluna ausente no ano.

|  Ano | Linhas entrada | Linhas silver | Descartadas (não FINALIZADA) | Duplicados removidos | Bairro não informado | Severidade vazia | vitimasfatais existe | vitimasfatais preenchida |
|-----:|---------------:|--------------:|-----------------------------:|---------------------:|---------------------:|-----------------:|---------------------:|-------------------------:|
| 2015 |           7273 |          5175 |                         2098 |                    0 |                    9 |                0 |                  não |                      n/a |
| 2016 |          11263 |          8519 |                         2744 |                    0 |                   10 |                4 |                  sim |                    0,43% |
| 2017 |          11758 |          9223 |                         2534 |                    1 |                    6 |               13 |                  sim |                    0,40% |
| 2018 |          11411 |          9494 |                         1917 |                    0 |                   18 |                4 |                  sim |                    0,28% |
| 2019 |          12062 |         10109 |                         1953 |                    0 |                  148 |                0 |                  sim |                    0,25% |
| 2020 |           4092 |          3496 |                          596 |                    0 |                   31 |                0 |                  sim |                    0,57% |
| 2021 |           2380 |          2095 |                          284 |                    1 |                    3 |                0 |                  sim |                  100,00% |
| 2022 |           2669 |          2391 |                          278 |                    0 |                    8 |                0 |                  sim |                  100,00% |
| 2023 |           4032 |          3575 |                          457 |                    0 |                   12 |                0 |                  sim |                  100,00% |
| 2024 |           5315 |          4929 |                          386 |                    0 |                    6 |                0 |                  sim |                  100,00% |

## Detalhe

|  Ano | Dup. linha idêntica | Dup. protocolo | Severidade fora padrão | Datas fora do ano | Bairros distintos | vitimasfatais vazias |
|-----:|--------------------:|---------------:|-----------------------:|------------------:|------------------:|---------------------:|
| 2015 |                   0 |              0 |                      0 |                 0 |                93 |                  n/a |
| 2016 |                   0 |              0 |                      0 |                 0 |                94 |                 8482 |
| 2017 |                   1 |              0 |                      0 |                 0 |                94 |                 9186 |
| 2018 |                   0 |              0 |                      0 |                 0 |                94 |                 9467 |
| 2019 |                   0 |              0 |                      2 |                 0 |                94 |                10084 |
| 2020 |                   0 |              0 |                      0 |                 0 |                92 |                 3476 |
| 2021 |                   1 |              0 |                      6 |                 0 |                89 |                    0 |
| 2022 |                   0 |              0 |                      0 |                 0 |                89 |                    0 |
| 2023 |                   0 |              0 |                      0 |                 0 |                92 |                    0 |
| 2024 |                   0 |              0 |                      0 |                32 |                94 |                    0 |
