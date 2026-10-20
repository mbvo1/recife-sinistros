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
    transform, _to_int, _to_int_ou_na, _trunca_hora, _limpa_protocolo,
    _detecta_coluna_severidade, _gera_relatorio_qualidade_md,
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
    deve virar "NÃO INFORMADO" (nunca ficar "" nem ser descartada), com o
    valor cru preservado em 'severidade_original' e sinalizada em
    'severidade_anomala'. Contada na métrica 'severidade_vazia_no_silver'.
    Achado real: 147 linhas assim no bruto de 2016 (mas a maioria é
    CANCELADA/PENDENTE; só 4 sobrevivem ao filtro FINALIZADA).
    """
    linhas = [_linha_2015(tipo="SEM VÍTIMA"), _linha_2015(tipo="")]
    caminho = _escreve_csv(tmp_path, linhas)
    df, m = transform(caminho, 2015)
    assert m["severidade_vazia_no_silver"] == 1
    assert df.loc[1, "severidade"] == "NÃO INFORMADO"
    assert df.loc[1, "severidade_original"] == ""
    assert bool(df.loc[1, "severidade_anomala"]) is True
    assert bool(df.loc[0, "severidade_anomala"]) is False


def test_severidade_fora_do_padrao_vira_nao_informado(tmp_path):
    """
    Severidade fora do padrão (ex.: "APOIO", vazamento de outro campo —
    achado real em 2019) também vira "NÃO INFORMADO" + flag, com o valor cru
    preservado, igual ao caso de severidade vazia — nunca é inventada nem
    silenciosamente descartada.
    """
    linhas = (
        [_linha_2015(natureza_acidente="SEM VÍTIMA") for _ in range(20)]
        + [_linha_2015(natureza_acidente="APOIO")]
    )
    for l in linhas:
        l.pop("natureza", None)
        l["tipo"] = "COLISÃO"
    caminho = _escreve_csv(tmp_path, linhas)
    df, m = transform(caminho, 2019)
    assert m["severidade_fora_padrao_no_silver"] == 1
    linha_anomala = df[df["severidade_original"] == "APOIO"].iloc[0]
    assert linha_anomala["severidade"] == "NÃO INFORMADO"
    assert bool(linha_anomala["severidade_anomala"]) is True
 
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
 
def test_data_fora_do_ano_e_sinalizada_mas_nao_corrigida(tmp_path):
    """
    Achado real em 2024: 32 linhas (silver) com data em dez/2025 dentro do
    arquivo de 2024, causa desconhecida. O transform NÃO corrige a data —
    só marca 'data_fora_do_ano'=True, preservando a data original.
    """
    linhas = [_linha_2024(Protocolo="1,0", data="2024-01-01"),
              _linha_2024(Protocolo="2,0", data="2025-12-31")]
    caminho = _escreve_csv(tmp_path, linhas)
    df, m = transform(caminho, 2024)
    assert m["datas_fora_do_ano"] == 1
    assert bool(df.loc[0, "data_fora_do_ano"]) is False
    assert bool(df.loc[1, "data_fora_do_ano"]) is True
    assert str(df.loc[1, "data"]) == "2025-12-31"  # data preservada, não corrigida


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


# --- Testes de dedup técnico (ADR-015) ------------------------------------

def test_dedup_remove_linha_identica(tmp_path):
    """
    Critério 1: linha idêntica em todas as colunas é registro em dobro.
    Achado real: 1 par assim em 2017 e 1 em 2021 (anos sem protocolo).
    """
    linhas = [_linha_2015(), _linha_2015(), _linha_2015(bairro="DERBY")]
    caminho = _escreve_csv(tmp_path, linhas)
    df, m = transform(caminho, 2015)
    assert m["linhas_silver"] == 2
    assert m["duplicados_linha_identica"] == 1
    assert m["duplicados_protocolo"] == 0
    assert list(df["bairro"]) == ["BOA VIAGEM", "DERBY"]


def test_dedup_remove_protocolo_repetido_mantendo_primeiro(tmp_path):
    """
    Critério 2: mesmo protocolo com conteúdo diferente (aqui, a hora) é o
    mesmo chamado registrado duas vezes. Fica a primeira ocorrência.
    """
    linhas = [_linha_2024(hora="06:05:00"), _linha_2024(hora="06:10:00")]
    caminho = _escreve_csv(tmp_path, linhas)
    df, m = transform(caminho, 2024)
    assert m["linhas_silver"] == 1
    assert m["duplicados_protocolo"] == 1
    assert m["duplicados_linha_identica"] == 0
    assert df.loc[0, "hora"] == "06:05:00"


def test_dedup_nao_remove_sinistros_distintos(tmp_path):
    """
    Não é duplicata: (a) conteúdo igual mas protocolos diferentes — dois
    chamados; (b) sem protocolo, mesmo local e hora mas um campo diferente
    (número de autos) — pode ser outro sinistro, não há como provar que não.
    """
    caminho = _escreve_csv(tmp_path, [
        _linha_2024(Protocolo="1,0"), _linha_2024(Protocolo="2,0"),
    ])
    _, m = transform(caminho, 2024)
    assert m["linhas_silver"] == 2
    assert m["duplicados_linha_identica"] + m["duplicados_protocolo"] == 0

    caminho = _escreve_csv(tmp_path, [_linha_2015(auto="1"), _linha_2015(auto="2")])
    _, m = transform(caminho, 2015)
    assert m["linhas_silver"] == 2
    assert m["duplicados_linha_identica"] + m["duplicados_protocolo"] == 0


def test_dedup_roda_depois_do_filtro_finalizada(tmp_path):
    """Par idêntico de CANCELADA conta só como descartada, nunca como
    duplicata — cada linha removida cai em uma única métrica."""
    linhas = [_linha_2015(), _linha_2015(situacao="CANCELADA"),
              _linha_2015(situacao="CANCELADA")]
    caminho = _escreve_csv(tmp_path, linhas)
    _, m = transform(caminho, 2015)
    assert m["descartadas_nao_finalizada"] == 2
    assert m["duplicados_linha_identica"] == 0

 
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


def test_to_int_ou_na_formatos():
    """Parser de vitimasfatais: igual a _to_int, exceto vazio -> NA."""
    assert _to_int_ou_na("1") == 1
    assert _to_int_ou_na("2,0") == 2    # vírgula decimal
    assert _to_int_ou_na("") is pd.NA   # vazio -> desconhecido, nunca 0
    assert _to_int_ou_na("lixo") is None


def test_vitimasfatais_celula_vazia_com_coluna_presente_vira_nulo(tmp_path):
    """
    Regressão do bug: em 2016-2020 a coluna 'vitimasfatais' existe mas está
    vazia em >99% das linhas. Antes, o vazio virava 0 e esses anos saíam
    como "zero mortes". Vazio deve virar NA (desconhecido), e ser contado
    na métrica 'vitimasfatais_vazias_no_silver'.
    """
    linhas = [_linha_2024(Protocolo="1,0", vitimasfatais=""),
              _linha_2024(Protocolo="2,0", vitimasfatais="1,0")]
    caminho = _escreve_csv(tmp_path, linhas)
    df, m = transform(caminho, 2024)
    assert pd.isna(df.loc[0, "vitimasfatais"])
    assert df.loc[1, "vitimasfatais"] == 1
    assert m["vitimasfatais_vazias_no_silver"] == 1


def test_contagem_vazia_continua_zero_com_vitimasfatais_vazia(tmp_path):
    """
    Regressão: o parser próprio de vitimasfatais NÃO pode vazar para as
    contagens de veículo — na mesma linha, 'moto' vazio continua 0 (ADR-006)
    enquanto 'vitimasfatais' vazio vira NA.
    """
    caminho = _escreve_csv(tmp_path, [_linha_2024(moto="", vitimasfatais="")])
    df, _ = transform(caminho, 2024)
    assert df.loc[0, "moto"] == 0
    assert pd.isna(df.loc[0, "vitimasfatais"])


def test_vitimasfatais_vazias_nao_se_aplica_quando_coluna_ausente(tmp_path):
    """2015 não tem a coluna: a métrica de vazias é None (não aplicável),
    não 0 — 0 implicaria que a coluna existia e estava toda preenchida."""
    caminho = _escreve_csv(tmp_path, [_linha_2015()])
    _, m = transform(caminho, 2015)
    assert m["vitimasfatais_vazias_no_silver"] is None
 
 
# --- Testes de limpeza de campos ------------------------------------------
 
def test_bairro_vazio_vira_nao_informado(tmp_path):
    caminho = _escreve_csv(tmp_path, [_linha_2015(bairro="   ")])
    df, _ = transform(caminho, 2015)
    assert df.loc[0, "bairro"] == "NÃO INFORMADO"
    assert df.loc[0, "bairro_original"] == "NÃO INFORMADO"


def test_bairro_normaliza_acento_preservando_original(tmp_path):
    """
    Achado real: 'HIPÓDROMO' (2015-2022) e 'HIPODROMO' (2023-2024) são o
    mesmo bairro com grafias diferentes. 'bairro' remove o acento de forma
    determinística para unificar; 'bairro_original' preserva a grafia crua.
    """
    linhas = [_linha_2015(bairro="HIPÓDROMO"), _linha_2015(bairro="HIPODROMO")]
    caminho = _escreve_csv(tmp_path, linhas)
    df, _ = transform(caminho, 2015)
    assert set(df["bairro"]) == {"HIPODROMO"}
    assert set(df["bairro_original"]) == {"HIPÓDROMO", "HIPODROMO"}
 
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

# --- Testes do relatório de qualidade -------------------------------------

def test_vitimasfatais_preenchimento_pct(tmp_path):
    """1 de 4 linhas preenchida => 25%. Coluna ausente => None, nunca 0%."""
    linhas = [_linha_2024(Protocolo=f"{i},0", vitimasfatais="") for i in range(3)]
    linhas.append(_linha_2024(Protocolo="9,0", vitimasfatais="1,0"))
    _, m = transform(_escreve_csv(tmp_path, linhas), 2024)
    assert m["vitimasfatais_preenchimento_pct"] == 25.0

    _, m = transform(_escreve_csv(tmp_path, [_linha_2015()]), 2015)
    assert m["vitimasfatais_preenchimento_pct"] is None


def test_relatorio_qualidade_mostra_na_quando_coluna_ausente(tmp_path):
    """O relatório escreve 'n/a' (não aplicável) para ano sem a coluna, e o
    percentual com vírgula decimal para ano com a coluna."""
    _, m2015 = transform(_escreve_csv(tmp_path, [_linha_2015()]), 2015)
    _, m2024 = transform(_escreve_csv(tmp_path, [_linha_2024()]), 2024)
    md = _gera_relatorio_qualidade_md([m2015, m2024])
    linha_2015 = next(l for l in md.splitlines() if l.startswith("| 2015"))
    linha_2024 = next(l for l in md.splitlines() if l.startswith("| 2024"))
    assert linha_2015.split("|")[-2].strip() == "n/a"
    assert linha_2024.split("|")[-2].strip() == "100,00%"
