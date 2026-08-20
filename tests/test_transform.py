"""
Testes do transform bronze->silver.
 
Estes testes NÃO dependem dos CSVs reais da CTTU. Cada teste escreve um CSV
minúsculo e sintético num diretório temporário e verifica um comportamento.
Assim a lógica crítica (swap, filtro, nulo de vitimasfatais) fica protegida
mesmo antes de você ter os 10 anos de dado.
 
Rodar:  pytest -v
"""
 
import pandas as pd
import pytest
 
from transform_sinistros import (
    transform, _to_int, _trunca_hora, _limpa_protocolo,
    _detecta_coluna_severidade,
)
 
 
# --- Helpers de fixture ---------------------------------------------------
 
def _escreve_csv(tmp_path, linhas: list[dict], nome="teste.csv"):
    """Escreve um CSV no formato bruto da CTTU (sep=';', UTF-8)."""
    caminho = tmp_path / nome
    pd.DataFrame(linhas).to_csv(caminho, sep=";", index=False, encoding="utf-8")
    return str(caminho)
 
 
# Linha-base no LAYOUT 2015 (tipo=severidade, natureza=espécie), FINALIZADA.
def _linha_2015(**over):
    base = {
        "tipo": "SEM VÍTIMA", "natureza": "COLISÃO", "situacao": "FINALIZADA",
        "data": "2015-06-01", "hora": "08:00:00.000", "bairro": "BOA VIAGEM",
        "endereco": "RUA X", "numero": "10", "complemento": "",
        "auto": "1", "moto": "", "ciclom": "", "ciclista": "", "pedestre": "",
        "onibus": "", "caminhao": "", "viatura": "", "outros": "", "vitimas": "0",
    }
    base.update(over)
    return base
 
 
# Linha-base no LAYOUT 2024 (natureza=severidade, tipo=espécie), com Protocolo
# e vitimasfatais, FINALIZADA.
def _linha_2024(**over):
    base = {
        "Protocolo": "292972,0", "natureza": "COM VÍTIMA", "tipo": "COLISÃO LATERAL",
        "situacao": "FINALIZADA", "data": "2024-01-01", "hora": "06:05:00",
        "bairro": "BOA VIAGEM", "endereco": "AV Y", "numero": "20", "complemento": "",
        "auto": "1,0", "moto": "0,0", "ciclom": "0,0", "ciclista": "0,0",
        "pedestre": "0,0", "onibus": "0,0", "caminhao": "0,0", "viatura": "0,0",
        "outros": "0,0", "vitimas": "1", "vitimasfatais": "0",
    }
    base.update(over)
    return base
 
 
# --- Testes dos helpers ---------------------------------------------------
 
def test_to_int_formatos():
    assert _to_int("1") == 1
    assert _to_int("2,0") == 2          # vírgula decimal
    assert _to_int("") == 0             # vazio -> 0
    assert _to_int("lixo") is None      # não-parseável sinaliza anomalia
 
def test_trunca_hora():
    assert _trunca_hora("11:36:00.000") == "11:36:00"
    assert _trunca_hora("06:05:00") == "06:05:00"
    assert _trunca_hora("") is None
 
def test_limpa_protocolo():
    assert _limpa_protocolo("292972,0") == "292972"
    assert _limpa_protocolo("") is None
 
 
# --- Testes do SWAP (o coração do transform) ------------------------------
 
def test_swap_layout_2015(tmp_path):
    """Em 2015 a severidade está em 'tipo'."""
    caminho = _escreve_csv(tmp_path, [_linha_2015()])
    df, m = transform(caminho, 2015)
    assert m["coluna_severidade_detectada"] == "tipo"
    assert df.loc[0, "severidade"] == "SEM VÍTIMA"
    assert df.loc[0, "tipo_sinistro"] == "COLISÃO"
 
def test_swap_layout_2024(tmp_path):
    """Em 2024 a severidade está em 'natureza' — coluna oposta a 2015."""
    caminho = _escreve_csv(tmp_path, [_linha_2024()])
    df, m = transform(caminho, 2024)
    assert m["coluna_severidade_detectada"] == "natureza"
    assert df.loc[0, "severidade"] == "COM VÍTIMA"
    assert df.loc[0, "tipo_sinistro"] == "COLISÃO LATERAL"
 
def test_layout_2016_natureza_acidente(tmp_path):
    """
    2016 usa o mesmo layout semântico de 2015 (espécie em 'tipo'), mas a
    coluna de SEVERIDADE se chama 'natureza_acidente', não 'natureza'.
    Achado ao rodar o transform nos dados reais (ver docs/decisions.md ADR-004).
    """
    linha = _linha_2015(tipo="COLISÃO")  # 'tipo' = espécie em 2016, não severidade
    linha.pop("natureza")                # 2016 não tem 'natureza'; tem natureza_acidente
    linha["natureza_acidente"] = "SEM VÍTIMA"
    caminho = _escreve_csv(tmp_path, [linha])
    df, m = transform(caminho, 2016)
    assert m["coluna_severidade_detectada"] == "natureza_acidente"
    assert m["coluna_especie_detectada"] == "tipo"
    assert df.loc[0, "severidade"] == "SEM VÍTIMA"
    assert df.loc[0, "tipo_sinistro"] == "COLISÃO"
 
def test_severidade_vazia_nao_quebra_e_e_contada(tmp_path):
    """
    Uma linha com severidade em branco não deve quebrar o transform (a coluna
    ainda é identificável pelas OUTRAS linhas válidas) nem sumir do silver:
    deve aparecer na métrica 'severidade_vazia_no_silver'.
    Achado real: 147 linhas assim em 2016 (natureza_acidente vazia).
    """
    linhas = [_linha_2015(tipo="SEM VÍTIMA"), _linha_2015(tipo="")]
    caminho = _escreve_csv(tmp_path, linhas)
    df, m = transform(caminho, 2015)
    assert m["severidade_vazia_no_silver"] == 1
    assert "" in set(df["severidade"])
 
def test_colunas_maiusculas_sao_normalizadas(tmp_path):
    """
    2018 usa 'DATA' (maiúscula) em vez de 'data'. Nomes de coluna devem ser
    normalizados para minúsculas independente de como vêm no CSV.
    Achado ao rodar o transform em 2018 real (ver docs/decisions.md ADR-004).
    """
    linha = _linha_2015()
    linha["DATA"] = linha.pop("data")
    caminho = _escreve_csv(tmp_path, [linha])
    df, m = transform(caminho, 2018)
    assert len(df) == 1
    assert str(df.loc[0, "data"]) == "2015-06-01"
 
def test_tolera_ruido_pontual_na_severidade(tmp_path):
    """
    2019: 'natureza_acidente' tem quase todos os valores válidos, mas 2 linhas
    trazem "ENTRADA E SAÍDA"/"APOIO" (vazamento de outro campo). A coluna deve
    ainda ser detectada como severidade (ruído << limiar), e a métrica deve
    contar as linhas fora do padrão em vez de escondê-las.
    Achado ao rodar o transform em 2019 real (ver docs/decisions.md ADR-004).
    """
    linhas = (
        [_linha_2015(natureza_acidente="SEM VÍTIMA") for _ in range(20)]
        + [_linha_2015(natureza_acidente="APOIO")]  # ruído: 1 de 21 = 4.8%
    )
    # Este caso usa o layout 2016+ (severidade em natureza_acidente).
    for l in linhas:
        l.pop("natureza", None)
        l["tipo"] = "COLISÃO"
    caminho = _escreve_csv(tmp_path, linhas)
    df, m = transform(caminho, 2019)
    assert m["coluna_severidade_detectada"] == "natureza_acidente"
    assert m["severidade_ruido_no_bruto"] == 1
 
def test_ruido_alto_ainda_falha(tmp_path):
    """Ruído ACIMA do limiar não deve ser tolerado — a detecção deve seguir
    falhando alto quando a coluna não é confiável de verdade."""
    linhas = [_linha_2015(tipo="VALOR ESTRANHO"), _linha_2015(tipo="VALOR ESTRANHO")]
    for l in linhas:
        l["natureza"] = "OUTRO ESTRANHO"
    caminho = _escreve_csv(tmp_path, linhas)
    with pytest.raises(ValueError):
        transform(caminho, 2099)
 
def test_deteccao_falha_alto(tmp_path):
    """Severidade irreconhecível deve levantar erro, não mapear errado."""
    linha = _linha_2015(tipo="VALOR ESTRANHO", natureza="OUTRO ESTRANHO")
    caminho = _escreve_csv(tmp_path, [linha])
    with pytest.raises(ValueError):
        transform(caminho, 2099)
 
 
# --- Testes do filtro de qualidade ----------------------------------------
 
def test_filtro_finalizada(tmp_path):
    linhas = [
        _linha_2015(situacao="FINALIZADA"),
        _linha_2015(situacao="CANCELADA"),
        _linha_2015(situacao="EM ATENDIMENTO"),
    ]
    caminho = _escreve_csv(tmp_path, linhas)
    df, m = transform(caminho, 2015)
    assert m["linhas_entrada"] == 3
    assert m["linhas_silver"] == 1
    assert m["descartadas_nao_finalizada"] == 2
 
 
# --- Testes de vitimasfatais (ausente => NULO, nunca 0) -------------------
 
def test_vitimasfatais_ausente_vira_nulo(tmp_path):
    """2015 não tem a coluna: silver deve trazer NA, não 0."""
    caminho = _escreve_csv(tmp_path, [_linha_2015()])
    df, _ = transform(caminho, 2015)
    assert pd.isna(df.loc[0, "vitimasfatais"])
 
def test_vitimasfatais_presente_parseia(tmp_path):
    caminho = _escreve_csv(tmp_path, [_linha_2024(vitimasfatais="2,0")])
    df, _ = transform(caminho, 2024)
    assert df.loc[0, "vitimasfatais"] == 2
 
 
# --- Testes de limpeza de campos ------------------------------------------
 
def test_bairro_vazio_vira_nao_informado(tmp_path):
    caminho = _escreve_csv(tmp_path, [_linha_2015(bairro="   ")])
    df, _ = transform(caminho, 2015)
    assert df.loc[0, "bairro"] == "NÃO INFORMADO"
 
def test_id_sintetico_quando_sem_protocolo(tmp_path):
    caminho = _escreve_csv(tmp_path, [_linha_2015()])
    df, _ = transform(caminho, 2015)
    assert df.loc[0, "id_sinistro"] == "2015-000000"
 
def test_protocolo_usado_quando_presente(tmp_path):
    caminho = _escreve_csv(tmp_path, [_linha_2024()])
    df, _ = transform(caminho, 2024)
    assert df.loc[0, "id_sinistro"] == "292972"
 
def test_contagem_vazia_vira_zero(tmp_path):
    caminho = _escreve_csv(tmp_path, [_linha_2015(moto="")])
    df, _ = transform(caminho, 2015)
    assert df.loc[0, "moto"] == 0