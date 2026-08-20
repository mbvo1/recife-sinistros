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
        "coluna_especie_detectada": col_tipo,
        "severidade_ruido_no_bruto": sev_linhas_ruido,
        "severidade_vazia_no_silver": int((out["severidade"] == "").sum()),
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
              f"| sev='{m['coluna_severidade_detectada']}' esp='{m['coluna_especie_detectada']}' "
              f"| sev_vazia={m['severidade_vazia_no_silver']:>4} "
              f"| sev_ruido={m['severidade_ruido_no_bruto']:>3} "
              f"| vitfatais={'sim' if m['tem_vitimasfatais'] else 'não'}")
 
    if not achou:
        print("\nNenhum CSV encontrado. Baixe os arquivos anuais do portal e "
              "coloque em data/raw/ (ver data/README.md).")