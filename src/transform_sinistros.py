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
  - 'vitimasfatais' ausente num ano => NULO, jamais 0.
  - Vazio em contagem de veículo => 0 (inferência documentada).
  - 'vitimas' mantido cru: o dicionário oficial afirma uma regra que o dado de
    2015 desmente, então não derivamos "total de vítimas".

Validado contra 2015 e 2024. Anos intermediários (2016-2023) precisam ser
rodados e conferidos — a detecção por valor foi desenhada pra aguentar, mas
é hipótese até você testar.
"""

from __future__ import annotations
import re
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
    ["id_sinistro", "ano", "data", "hora", "severidade", "tipo_sinistro",
     "bairro", "endereco", "numero", "complemento"]
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


def _trunca_hora(v: str):
    """'11:36:00.000' -> '11:36:00' ; '06:05:00' -> '06:05:00'."""
    s = str(v).strip()
    if s == "":
        return None
    return s.split(".")[0][:8]


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

def _detecta_coluna_severidade(df: pd.DataFrame) -> str:
    """
    Descobre QUAL coluna ('tipo' ou 'natureza') carrega a severidade,
    checando de qual delas os valores são subconjunto de SEVERIDADE_VALIDAS.
    Neutraliza o swap sem depender do ano. Falha alto (ValueError) se nenhuma
    bater — melhor erro explícito do que mapeamento errado silencioso.
    """
    candidatas = [c for c in ("tipo", "natureza") if c in df.columns]
    for col in candidatas:
        valores = {_norm_texto(x).upper() for x in df[col] if _norm_texto(x)}
        if valores and valores <= SEVERIDADE_VALIDAS:
            return col
    raise ValueError(
        "Nenhuma coluna 'tipo'/'natureza' bate com os valores de severidade "
        f"esperados {SEVERIDADE_VALIDAS}. Revisar manualmente. "
        f"Colunas disponíveis: {list(df.columns)}"
    )


# --- Transformação principal ---------------------------------------------

def transform(caminho_csv: str, ano: int) -> tuple[pd.DataFrame, dict]:
    """
    Lê um CSV bruto anual e devolve (df_silver, metricas).
    'metricas' é o dicionário que, na Lambda, vira métricas do CloudWatch.
    """
    bruto = pd.read_csv(
        caminho_csv, sep=";", encoding="utf-8", dtype=str, keep_default_na=False
    )
    bruto.columns = [c.strip() for c in bruto.columns]
    linhas_entrada = len(bruto)

    # Resolve o swap: identifica papéis reais das colunas.
    col_sev = _detecta_coluna_severidade(bruto)
    col_tipo = "natureza" if col_sev == "tipo" else "tipo"

    out = pd.DataFrame()

    # Chave: Protocolo nativo (2017+) ou sintético (anos sem chave).
    if "Protocolo" in bruto.columns:
        out["id_sinistro"] = bruto["Protocolo"].map(_limpa_protocolo)
    else:
        out["id_sinistro"] = [f"{ano}-{i:06d}" for i in range(linhas_entrada)]

    out["ano"] = ano
    out["data"] = pd.to_datetime(
        bruto["data"].str.strip(), format="%Y-%m-%d", errors="coerce"
    ).dt.date
    out["hora"] = bruto["hora"].map(_trunca_hora)

    out["severidade"] = bruto[col_sev].map(lambda x: _norm_texto(x).upper())
    out["tipo_sinistro"] = (
        bruto[col_tipo].map(lambda x: _norm_texto(x).upper())
        if col_tipo in bruto.columns else ""
    )

    out["bairro"] = bruto["bairro"].map(lambda x: _norm_texto(x).upper())
    out.loc[out["bairro"] == "", "bairro"] = "NÃO INFORMADO"

    for c in ["endereco", "numero", "complemento"]:
        out[c] = bruto[c].map(_norm_texto) if c in bruto.columns else ""

    for c in COLS_CONTAGEM:
        out[c] = bruto[c].map(_to_int) if c in bruto.columns else 0

    out["vitimas"] = bruto["vitimas"].map(_to_int) if "vitimas" in bruto.columns else 0

    # vitimasfatais: coluna ausente no ano => NULO (nunca 0).
    if "vitimasfatais" in bruto.columns:
        out["vitimasfatais"] = bruto["vitimasfatais"].map(_to_int)
    else:
        out["vitimasfatais"] = pd.NA

    situacao = bruto["situacao"].map(lambda x: _norm_texto(x).upper())

    # Filtro de qualidade: só acidentes confirmados.
    mask_final = situacao == "FINALIZADA"
    out = out[mask_final.values].reset_index(drop=True)

    out = out[COLS_SILVER]

    metricas = {
        "ano": ano,
        "linhas_entrada": linhas_entrada,
        "linhas_silver": len(out),
        "descartadas_nao_finalizada": int((~mask_final).sum()),
        "coluna_severidade_detectada": col_sev,
        "datas_invalidas": int(out["data"].isna().sum()),
        "contagens_nao_parseaveis": int(out[COLS_CONTAGEM].isna().any(axis=1).sum()),
        "bairros_nao_informados": int((out["bairro"] == "NÃO INFORMADO").sum()),
        "tem_vitimasfatais": "vitimasfatais" in bruto.columns,
    }
    return out, metricas


# --- Execução local: varre todos os anos de data/raw ---------------------

if __name__ == "__main__":
    from pathlib import Path

    RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
    ANOS = range(2015, 2025)  # 2015..2024

    print(f"Procurando CSVs em: {RAW}\n")
    achou = False
    for ano in ANOS:
        # Aceita o nome limpo; ajuste o padrão se seus arquivos tiverem outro.
        candidatos = list(RAW.glob(f"*{ano}*.csv"))
        if not candidatos:
            print(f"  {ano}: (arquivo não encontrado — pulei)")
            continue
        achou = True
        df, m = transform(str(candidatos[0]), ano)
        print(f"  {ano}: {m['linhas_entrada']:>6} -> {m['linhas_silver']:>6} silver "
              f"| descartadas={m['descartadas_nao_finalizada']:>5} "
              f"| sev='{m['coluna_severidade_detectada']}' "
              f"| vitfatais={'sim' if m['tem_vitimasfatais'] else 'não'}")

    if not achou:
        print("\nNenhum CSV encontrado. Baixe os arquivos anuais do portal e "
              "coloque em data/raw/ (ver data/README.md).")
