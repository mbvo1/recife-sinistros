"""
transform_sinistros.py
----------------------
Transformação bronze -> silver dos dados de sinistros de trânsito da CTTU
(Portal de Dados Abertos do Recife, licença ODbL).
 
Pega um CSV bruto anual (camada bronze, cópia fiel do que a CTTU publicou) e
devolve um DataFrame canônico, limpo e comparável entre anos (camada silver).
Python puro + pandas: roda na sua máquina, sem AWS, sem custo. Esta MESMA
função é depois embrulhada dentro da Lambda (ver src/handler.py, fase futura).
 
As decisões de projeto embutidas aqui estão documentadas em docs/decisions.md.
Resumo do que mais pega gente de surpresa:

  - SWAP tipo<->natureza: o significado de 'tipo' e 'natureza' inverteu entre
    2015 e 2024. NÃO mapeamos por nome de coluna; detectamos qual coluna é
    SEVERIDADE pelos VALORES (ver _detecta_coluna_severidade).
  - 'vitimasfatais' ausente num ano => NULO, jamais 0. Célula vazia com a
    coluna presente (comum em 2016-2020) também => NULO: vazio ali é
    "desconhecido", não "zero mortes" (ver ADR-006 e ADR-014).
  - Vazio em contagem de veículo => 0 (inferência documentada).
  - 'vitimas' mantido cru: o dicionário oficial afirma uma regra que o dado de
    2015 desmente, então não derivamos "total de vítimas".
  - Anomalias de qualidade NUNCA são corrigidas ou descartadas em silêncio:
    são marcadas com uma coluna booleana de flag e o valor original é
    preservado numa coluna '_original' quando a célula é reescrita. Ver
    'data_fora_do_ano', 'severidade_anomala'/'severidade_original',
    'bairro_original' e ADR-014.

Validado contra os 10 anos reais (2015-2024): roda sem erro, 18 testes
passam, e a varredura de qualidade por ano foi conferida manualmente — ver
docs/decisions.md (ADR-014) e docs/ROADMAP.md.
"""

from __future__ import annotations
import re
import unicodedata
import pandas as pd
 
 
# --- Constantes -----------------------------------------------------------
 
# Os três (e apenas três) valores de SEVERIDADE observados no dado real.
# Usados para DETECTAR qual coluna carrega severidade, seja qual for o nome.
SEVERIDADE_VALIDAS = {"SEM VÍTIMA", "COM VÍTIMA", "VÍTIMA FATAL"}
 
# Colunas de contagem (inteiros; vazio -> 0).
COLS_CONTAGEM = ["auto", "moto", "ciclom", "ciclista", "pedestre",
                 "onibus", "caminhao", "viatura", "outros"]
 
# Ordem final das colunas do silver.
COLS_SILVER = (
    ["id_sinistro", "ano", "data", "data_fora_do_ano", "hora",
     "severidade", "severidade_original", "severidade_anomala", "tipo_sinistro",
     "bairro", "bairro_original", "endereco", "numero", "complemento"]
    + COLS_CONTAGEM
    + ["vitimas", "vitimasfatais"]
)
 
 
# --- Helpers de limpeza ---------------------------------------------------
 
def _norm_texto(v: str) -> str:
    """Tira espaços das pontas e colapsa espaços internos. Preserva acentos."""
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v).strip())
 
 
def _to_int(v: str):
    """
    '1'   -> 1
    '2,0' -> 2   (vírgula decimal brasileira)
    ''    -> 0   (vazio interpretado como 'nenhum' — inferência documentada)
    lixo  -> None (sinaliza anomalia em vez de mascarar)
    """
    s = str(v).strip().replace(",", ".")
    if s == "" or s.lower() == "nan":
        return 0
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def _to_int_ou_na(v: str):
    """
    Parser próprio de 'vitimasfatais'. Igual a _to_int, EXCETO no vazio:
    '1'   -> 1
    '2,0' -> 2
    ''    -> pd.NA (desconhecido — NUNCA 0; ver ADR-006)
    lixo  -> None (sinaliza anomalia em vez de mascarar)
    Achado real: em 2016-2020 a coluna existe mas >99% das células estão
    vazias. Ler esse vazio como 0 afirmaria "zero mortes" sem base no dado.
    """
    s = str(v).strip().replace(",", ".")
    if s == "" or s.lower() == "nan":
        return pd.NA
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def _trunca_hora(v: str):
    """'11:36:00.000' -> '11:36:00' ; '06:05:00' -> '06:05:00'."""
    s = str(v).strip()
    if s == "":
        return None
    return s.split(".")[0][:8]
 
 
def _remove_acentos(v: str) -> str:
    """
    'HIPÓDROMO' -> 'HIPODROMO'. Normalização determinística de acento (sem
    dependência externa, só unicodedata da stdlib), usada para unificar
    grafias de bairro entre anos (achado real: 'HIPÓDROMO' em 2015-2022 vs
    'HIPODROMO' em 2023-2024). O valor com acento original é preservado em
    'bairro_original'.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", v) if unicodedata.category(c) != "Mn"
    )


def _limpa_protocolo(v: str):
    """'292972,0' -> '292972' (foi exportado como float com vírgula)."""
    s = str(v).strip().replace(",", ".")
    if s == "":
        return None
    try:
        return str(int(float(s)))
    except ValueError:
        return s  # mantém o valor bruto se não for numérico
 
 
# --- Detecção do swap tipo/natureza --------------------------------------
 
# Nomes de coluna já observados carregando SEVERIDADE, em anos diferentes:
#   2015, 2016 -> natureza / natureza_acidente ficam vazias em 2016; severidade
#                 real de 2016 está em 'natureza_acidente'. 2024 -> 'natureza'.
#                 'tipo' carrega severidade em 2015. Ver docs/decisions.md ADR-004.
COLUNAS_CANDIDATAS_SEVERIDADE = ("tipo", "natureza", "natureza_acidente")
 
# Nomes de coluna já observados carregando ESPÉCIE do sinistro (o "outro" campo).
COLUNAS_CANDIDATAS_ESPECIE = ("tipo", "natureza", "natureza_acidente")
 
 
# Proporção mínima de linhas (não-vazias) que precisam bater com
# SEVERIDADE_VALIDAS para uma coluna ser aceita como severidade. Não é 100%
# porque dados reais têm ruído — ex.: em 2019, 2 de ~12.000 linhas de
# 'natureza_acidente' trazem "ENTRADA E SAÍDA"/"APOIO" (vazamento de outro
# campo, aparentemente administrativo). Ver docs/decisions.md ADR-004.
LIMIAR_SEVERIDADE_VALIDA = 0.95
 
 
def _detecta_coluna_severidade(df: pd.DataFrame) -> tuple[str, int]:
    """
    Descobre QUAL coluna carrega a severidade: a primeira candidata cuja
    proporção de linhas (não-vazias) batendo com SEVERIDADE_VALIDAS atinge
    LIMIAR_SEVERIDADE_VALIDA. Não exige 100% — tolera ruído pontual, que é
    reportado nas métricas, não escondido.
    Neutraliza o swap/rename sem depender do ano. Falha alto (ValueError) se
    nenhuma candidata atingir o limiar — melhor erro explícito do que
    mapeamento errado silencioso.
    Retorna (nome_da_coluna, quantidade_de_linhas_fora_do_padrão).
    """
    candidatas = [c for c in COLUNAS_CANDIDATAS_SEVERIDADE if c in df.columns]
    melhor = None  # (col, proporcao_valida, n_invalidas) do melhor candidato visto
    for col in candidatas:
        serie = df[col].map(lambda x: _norm_texto(x).upper())
        preenchidas = serie[serie != ""]
        if len(preenchidas) == 0:
            continue
        validas = preenchidas.isin(SEVERIDADE_VALIDAS)
        proporcao = validas.mean()
        n_invalidas = int((~validas).sum())
        if proporcao >= LIMIAR_SEVERIDADE_VALIDA:
            return col, n_invalidas
        if melhor is None or proporcao > melhor[1]:
            melhor = (col, proporcao, n_invalidas)
    detalhe_melhor = (
        f" Melhor candidata foi '{melhor[0]}' com {melhor[1]:.1%} de linhas válidas."
        if melhor else ""
    )
    raise ValueError(
        "Nenhuma coluna candidata atinge o limiar de "
        f"{LIMIAR_SEVERIDADE_VALIDA:.0%} de valores de severidade "
        f"esperados {SEVERIDADE_VALIDAS}. Revisar manualmente.{detalhe_melhor} "
        f"Candidatas testadas: {candidatas}. "
        f"Colunas disponíveis: {list(df.columns)}"
    )
 
 
def _detecta_coluna_especie(df: pd.DataFrame, col_severidade: str) -> str | None:
    """
    Descobre a coluna de ESPÉCIE do sinistro (COLISÃO, ATROPELAMENTO...):
    é a candidata de espécie/severidade que EXISTE no arquivo e NÃO é a
    coluna já identificada como severidade. Retorna None se não achar
    nenhuma (métrica registra isso; tipo_sinistro fica vazio nesse ano).
    """
    for col in COLUNAS_CANDIDATAS_ESPECIE:
        if col in df.columns and col != col_severidade:
            return col
    return None
 
 
# --- Transformação principal ---------------------------------------------
 
def transform(caminho_csv: str, ano: int) -> tuple[pd.DataFrame, dict]:
    """
    Lê um CSV bruto anual e devolve (df_silver, metricas).
    'metricas' é o dicionário que, na Lambda, vira métricas do CloudWatch.
    """
    bruto = pd.read_csv(
        caminho_csv, sep=";", encoding="utf-8", dtype=str, keep_default_na=False
    )
    # Normaliza nomes de coluna: tira espaço e força minúsculas. Necessário
    # porque o portal varia a caixa entre anos (ex.: 'DATA' em 2018 vs 'data'
    # nos demais). Ver docs/decisions.md ADR-004.
    bruto.columns = [c.strip().lower() for c in bruto.columns]
    linhas_entrada = len(bruto)
 
    # Resolve o swap/rename: identifica papéis reais das colunas.
    col_sev, sev_linhas_ruido = _detecta_coluna_severidade(bruto)
    col_tipo = _detecta_coluna_especie(bruto, col_sev)
 
    out = pd.DataFrame()
 
    # Chave: protocolo nativo (2017+) ou sintético (anos sem chave).
    if "protocolo" in bruto.columns:
        out["id_sinistro"] = bruto["protocolo"].map(_limpa_protocolo)
    else:
        out["id_sinistro"] = [f"{ano}-{i:06d}" for i in range(linhas_entrada)]
 
    out["ano"] = ano
    data_dt = pd.to_datetime(
        bruto["data"].str.strip(), format="%Y-%m-%d", errors="coerce"
    )
    out["data"] = data_dt.dt.date
    # Sinaliza data fora do ano do próprio arquivo (achado real em 2024: 32
    # linhas com data em dez/2025, causa desconhecida). NÃO corrige a data —
    # só marca, para quem for analisar decidir o que fazer. Ver ADR-014.
    out["data_fora_do_ano"] = ((data_dt.dt.year != ano) & data_dt.notna()).values
    out["hora"] = bruto["hora"].map(_trunca_hora)

    # Severidade vazia ou fora do padrão (ex.: "APOIO", "OUTROS" — vazamento
    # de outro campo ou valor genérico do sistema de origem) NUNCA é
    # descartada nem inventada: o valor cru fica em 'severidade_original' e
    # 'severidade' recebe "NÃO INFORMADO", com 'severidade_anomala'=True.
    # Ver ADR-014.
    severidade_bruta = bruto[col_sev].map(lambda x: _norm_texto(x).upper())
    severidade_anomala = ~severidade_bruta.isin(SEVERIDADE_VALIDAS)
    out["severidade_original"] = severidade_bruta.values
    out["severidade"] = severidade_bruta.where(~severidade_anomala, "NÃO INFORMADO").values
    out["severidade_anomala"] = severidade_anomala.values

    out["tipo_sinistro"] = (
        bruto[col_tipo].map(lambda x: _norm_texto(x).upper())
        if col_tipo in bruto.columns else ""
    )

    # Bairro: grafia original preservada em 'bairro_original'; 'bairro' leva
    # a normalização determinística de acento (achado real: 'HIPÓDROMO' em
    # 2015-2022 vs 'HIPODROMO' em 2023-2024). O marcador "NÃO INFORMADO" é
    # vocabulário controlado, não dado bruto — fica de fora da normalização
    # de acento para não virar "NAO INFORMADO" e quebrar a métrica abaixo.
    # Ver ADR-014.
    bairro_bruto = bruto["bairro"].map(lambda x: _norm_texto(x).upper())
    bairro_vazio = bairro_bruto == ""
    out["bairro_original"] = bairro_bruto.where(~bairro_vazio, "NÃO INFORMADO").values
    out["bairro"] = (
        bairro_bruto.map(_remove_acentos).where(~bairro_vazio, "NÃO INFORMADO").values
    )

    for c in ["endereco", "numero", "complemento"]:
        out[c] = bruto[c].map(_norm_texto) if c in bruto.columns else ""

    for c in COLS_CONTAGEM:
        out[c] = bruto[c].map(_to_int) if c in bruto.columns else 0

    out["vitimas"] = bruto["vitimas"].map(_to_int) if "vitimas" in bruto.columns else 0

    # vitimasfatais: coluna ausente no ano => NULO (nunca 0). Coluna presente
    # com CÉLULA vazia (achado real: >99% vazia em 2016-2020) => NULO também,
    # via parser próprio (_to_int_ou_na) — diferente das contagens de
    # veículo. '_vitimasfatais_vazia' é auxiliar só para a métrica; não vai
    # para o silver. Ver ADR-006 e ADR-014.
    tem_vitimasfatais = "vitimasfatais" in bruto.columns
    if tem_vitimasfatais:
        out["vitimasfatais"] = bruto["vitimasfatais"].map(_to_int_ou_na)
        out["_vitimasfatais_vazia"] = (
            bruto["vitimasfatais"].map(lambda x: _norm_texto(x) == "").values
        )
    else:
        out["vitimasfatais"] = pd.NA
 
    situacao = bruto["situacao"].map(lambda x: _norm_texto(x).upper())
 
    # Filtro de qualidade: só acidentes confirmados.
    mask_final = situacao == "FINALIZADA"
    out = out[mask_final.values].reset_index(drop=True)

    # Contado antes da projeção final, que descarta a coluna auxiliar.
    # None quando a coluna nem existe no ano: não aplicável, não "zero vazias".
    vitimasfatais_vazias = (
        int(out["_vitimasfatais_vazia"].sum()) if tem_vitimasfatais else None
    )
    out = out[COLS_SILVER]
 
    metricas = {
        "ano": ano,
        "linhas_entrada": linhas_entrada,
        "linhas_silver": len(out),
        "descartadas_nao_finalizada": int((~mask_final).sum()),
        "coluna_severidade_detectada": col_sev,
        "coluna_especie_detectada": col_tipo,
        "severidade_ruido_no_bruto": sev_linhas_ruido,
        "severidade_vazia_no_silver": int((out["severidade_original"] == "").sum()),
        "severidade_fora_padrao_no_silver": int(
            ((out["severidade_original"] != "") & out["severidade_anomala"]).sum()
        ),
        "datas_invalidas": int(out["data"].isna().sum()),
        "datas_fora_do_ano": int(out["data_fora_do_ano"].sum()),
        "contagens_nao_parseaveis": int(out[COLS_CONTAGEM].isna().any(axis=1).sum()),
        "bairros_nao_informados": int((out["bairro"] == "NÃO INFORMADO").sum()),
        "bairros_distintos": int(out["bairro"].nunique()),
        "tem_vitimasfatais": tem_vitimasfatais,
        "vitimasfatais_vazias_no_silver": vitimasfatais_vazias,
    }
    return out, metricas
 
 
# --- Relatório de qualidade -----------------------------------------------

def _gera_relatorio_qualidade_md(lista_metricas: list[dict]) -> str:
    """
    Monta uma tabela Markdown (uma linha por ano) com as métricas de
    qualidade, para citar em README/portfólio. Não decide nada — só expõe os
    números já calculados por transform().
    """
    colunas = [
        ("ano", "Ano"),
        ("linhas_entrada", "Linhas bruto"),
        ("linhas_silver", "Linhas silver"),
        ("descartadas_nao_finalizada", "Descartadas (não finalizada)"),
        ("severidade_vazia_no_silver", "Severidade vazia"),
        ("severidade_fora_padrao_no_silver", "Severidade fora padrão"),
        ("datas_fora_do_ano", "Datas fora do ano"),
        ("bairros_nao_informados", "Bairro não informado"),
        ("bairros_distintos", "Bairros distintos"),
        ("vitimasfatais_vazias_no_silver", "vitimasfatais vazias"),
    ]
    linhas = ["# Relatório de qualidade — camada silver", ""]
    linhas.append("Gerado por `src/transform_sinistros.py`. Ver `docs/decisions.md` (ADR-014) "
                   "para o porquê de cada métrica.")
    linhas.append("")
    linhas.append("| " + " | ".join(titulo for _, titulo in colunas) + " |")
    linhas.append("|" + "---|" * len(colunas))
    for m in lista_metricas:
        linhas.append("| " + " | ".join(str(m[chave]) for chave, _ in colunas) + " |")
    linhas.append("")
    return "\n".join(linhas)


# --- Execução local: varre todos os anos de data/raw, grava o silver -----

if __name__ == "__main__":
    from pathlib import Path

    RAIZ = Path(__file__).resolve().parents[1]
    RAW = RAIZ / "data" / "raw"
    SILVER = RAIZ / "data" / "silver"
    ANOS = range(2015, 2025)  # 2015..2024

    print(f"Procurando CSVs em: {RAW}\n")
    SILVER.mkdir(parents=True, exist_ok=True)

    achou = False
    todas_metricas = []
    silver_por_ano = []
    gravados = []  # (caminho, linhas) de cada arquivo escrito em disco
    for ano in ANOS:
        # Aceita o nome limpo; ajuste o padrão se seus arquivos tiverem outro.
        candidatos = list(RAW.glob(f"*{ano}*.csv"))
        if not candidatos:
            print(f"  {ano}: (arquivo não encontrado — pulei)")
            continue
        achou = True
        df, m = transform(str(candidatos[0]), ano)
        todas_metricas.append(m)
        silver_por_ano.append(df)

        destino = SILVER / f"sinistros_{ano}.csv"
        df.to_csv(destino, sep=";", index=False, encoding="utf-8")
        gravados.append((destino, len(df)))

        print(f"  {ano}: {m['linhas_entrada']:>6} -> {m['linhas_silver']:>6} silver "
              f"| descartadas={m['descartadas_nao_finalizada']:>5} "
              f"| sev='{m['coluna_severidade_detectada']}' esp='{m['coluna_especie_detectada']}' "
              f"| sev_vazia={m['severidade_vazia_no_silver']:>4} "
              f"| sev_fora_padrao={m['severidade_fora_padrao_no_silver']:>2} "
              f"| datas_fora_do_ano={m['datas_fora_do_ano']:>3} "
              f"| vitfatais={'sim' if m['tem_vitimasfatais'] else 'não'} "
              f"-> {destino.name}")

    if not achou:
        print("\nNenhum CSV encontrado. Baixe os arquivos anuais do portal e "
              "coloque em data/raw/ (ver data/README.md).")
    else:
        # Consolidado: só os anos efetivamente encontrados. Se faltar algum,
        # avisa — o arquivo NÃO representa os 10 anos nesse caso.
        consolidado = pd.concat(silver_por_ano, ignore_index=True)
        destino_consolidado = SILVER / "sinistros_consolidado.csv"
        consolidado.to_csv(destino_consolidado, sep=";", index=False, encoding="utf-8")
        gravados.append((destino_consolidado, len(consolidado)))
        anos_gravados = [m["ano"] for m in todas_metricas]
        if len(anos_gravados) != len(ANOS):
            print(f"\nATENÇÃO: consolidado cobre só {anos_gravados}, não os {len(ANOS)} anos.")

        print("\nArquivos gravados:")
        for caminho, n in gravados:
            print(f"  {caminho}  ({n} linhas)")

        relatorio = _gera_relatorio_qualidade_md(todas_metricas)
        destino_relatorio = RAIZ / "docs" / "relatorio_qualidade_silver.md"
        destino_relatorio.write_text(relatorio, encoding="utf-8")
        print(f"\nRelatório de qualidade gravado em: {destino_relatorio}")