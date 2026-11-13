from datetime import datetime, timedelta, timezone

import pytest
import requests

from app import dataCollector as collectors


FIM = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
INICIO = FIM - timedelta(hours=24)


def collector(**kwargs):
    cls = getattr(collectors, "CepdecCollector", None)
    assert cls is not None, "CepdecCollector precisa ser implementado"
    return cls(
        base_url="https://simet.example", token_url="https://auth.example/token",
        client_id="client", client_secret="segredo", api_key="chave",
        estacoes_dict=kwargs.pop("estacoes_dict", {"EMA_ADN_01": "ÁGUA DOCE DO NORTE"}),
        **kwargs,
    )


def leitura(ts, chuva=0.2, estacao="EMA_ADN_01", **kwargs):
    return {
        "estacao_codigo": estacao, "data_hora_utc": ts.isoformat(),
        "intervalo_minutos": 15, "qualidade": "VALIDO", "flags": [],
        "dados": {"PRECIPITACAO_MM": chuva}, **kwargs,
    }


def payload(rows, **kwargs):
    return {"inicio": INICIO, "fim": FIM, "leituras": {"EMA_ADN_01": rows},
            "metadados": {}, "erros": {}, "avisos": [], **kwargs}


def test_soma_apenas_24h_sem_duplicatas_e_sem_confundir_outros_sensores():
    item = leitura(FIM, 2.5)
    df = collector().process(payload([
        leitura(INICIO, 99), leitura(INICIO - timedelta(minutes=15), 99),
        leitura(FIM + timedelta(seconds=1), 99), item, dict(item),
        leitura(FIM - timedelta(minutes=15), "1,2"),
        leitura(FIM - timedelta(minutes=30), 100, estacao="OUTRA"),
    ]))
    assert df.iloc[0]["Prec_mm"] == 3.7
    assert df.iloc[0]["Fonte"] == "CEPDEC"
    assert "2/96" in df.iloc[0]["Observação"]
    assert df.attrs["avisos"]


def test_serie_completa_sem_chuva_nao_e_falha():
    rows = [leitura(FIM - timedelta(minutes=15*i), 0) for i in range(96)]
    df = collector().process(payload(rows))
    assert len(df) == 1
    assert df.iloc[0]["Prec_mm"] == 0
    assert df.iloc[0]["Observação"] == ""
    assert df.attrs["avisos"] == []


@pytest.mark.parametrize("valor", [None, "", "erro", -1, float("nan"), float("inf"), True])
def test_valor_invalido_nao_vira_leitura_de_zero(valor):
    df = collector().process(payload([leitura(FIM, valor)]))
    assert df.empty
    assert df.attrs["avisos"]


def test_qualidade_invalida_e_intervalo_errado_sao_descartados():
    df = collector().process(payload([
        leitura(FIM, 99, qualidade="INVALIDO"),
        leitura(FIM, 99, intervalo_minutos=60),
        leitura(FIM, 99, flags=["SUSPEITO"]),
        leitura(FIM - timedelta(minutes=15), 2),
    ]))
    assert df.iloc[0]["Prec_mm"] == 2
    assert df.attrs["avisos"]


def test_duas_estacoes_de_vargem_alta_permanecem_separadas():
    c = collector(estacoes_dict={"EMA_VAR_01": "VARGEM ALTA", "EMA_VAR_P_01": "VARGEM ALTA"})
    df = c.process(payload([], leituras={
        "EMA_VAR_01": [leitura(FIM, 2, "EMA_VAR_01")],
        "EMA_VAR_P_01": [leitura(FIM, 4, "EMA_VAR_P_01")],
    }))
    assert len(collectors.Joiner.all_records(df)) == 2
    assert collectors.Joiner.join(df).iloc[0]["Prec_mm"] == 4
    assert collectors.Joiner.join(df).iloc[0]["Observação"]


def response(body, status=200):
    import json
    r = requests.Response()
    r.status_code = status
    r.url = "https://simet.example/?token=NAO_EXIBIR"
    r._content = json.dumps(body).encode()
    return r


def mock_auth(monkeypatch):
    def post(url, **kw):
        assert url == "https://auth.example/token"
        assert kw["data"] == {"grant_type": "client_credentials", "client_id": "client", "client_secret": "segredo"}
        assert kw["timeout"] > 0
        return response({"access_token": "token"})
    monkeypatch.setattr(collectors.requests, "post", post)


def test_fetch_pagina_ate_inicio_da_janela_e_usa_metadados(monkeypatch):
    mock_auth(monkeypatch)
    calls = []
    def get(url, **kw):
        assert kw["headers"] == {"Authorization": "Bearer token", "x-api-key": "chave"}
        if url.endswith("/estacoes"):
            return response([{"codigo": "EMA_ADN_01", "latitude": -18.5, "longitude": -40.9, "altitude_m": 246}])
        params = kw["params"]
        calls.append(dict(params))
        assert params["estacao"] == "EMA_ADN_01"
        assert params["intervalo_minutos"] == 15
        if "cursor" not in params:
            return response({"items": [leitura(FIM, 2)], "next_cursor": "pagina2"})
        assert params["cursor"] == "pagina2"
        return response({"items": [leitura(FIM - timedelta(hours=1), 3), leitura(INICIO, 99)], "next_cursor": "nao_buscar"})
    monkeypatch.setattr(collectors.requests, "get", get)
    df = collector().fetch(now=FIM)
    assert len(calls) == 2
    assert df.iloc[0]["Prec_mm"] == 5
    assert df.iloc[0]["Latitude"] == -18.5


def test_falha_na_pagina_posterior_preserva_soma_e_avisa_sem_vazar_token(monkeypatch):
    mock_auth(monkeypatch)
    def get(url, **kw):
        if url.endswith("/estacoes"):
            return response([])
        if "cursor" in kw["params"]:
            return response({}, 503)
        return response({"items": [leitura(FIM, 4)], "next_cursor": "proxima"})
    monkeypatch.setattr(collectors.requests, "get", get)
    df = collector().fetch(now=FIM)
    assert df.iloc[0]["Prec_mm"] == 4
    assert "HTTP 503" in str(df.attrs["avisos"])
    assert "NAO_EXIBIR" not in str(df.attrs["avisos"])
    assert df.iloc[0]["Observação"]


def test_falha_em_todas_as_estacoes_nao_e_sucesso_vazio(monkeypatch):
    mock_auth(monkeypatch)
    monkeypatch.setattr(collectors.requests, "get", lambda *a, **kw: response({}, 503))
    with pytest.raises(RuntimeError, match="HTTP 503") as exc:
        collector().fetch(now=FIM)
    assert "NAO_EXIBIR" not in str(exc.value)


def test_cursor_repetido_nao_entra_em_loop(monkeypatch):
    mock_auth(monkeypatch)
    calls = []
    def get(url, **kw):
        if url.endswith("/estacoes"):
            return response([])
        calls.append(1)
        assert len(calls) <= 2
        return response({"items": [leitura(FIM, 1)], "next_cursor": "repetido"})
    monkeypatch.setattr(collectors.requests, "get", get)
    df = collector().fetch(now=FIM)
    assert df.iloc[0]["Prec_mm"] == 1
    assert "paginação" in str(df.attrs["avisos"]).lower()


def test_falha_de_token_e_sanitizada(monkeypatch):
    monkeypatch.setattr(collectors.requests, "post", lambda *a, **kw: response({}, 401))
    with pytest.raises(RuntimeError, match="HTTP 401") as exc:
        collector().fetch(now=FIM)
    assert "NAO_EXIBIR" not in str(exc.value)


def test_payload_malformado_nao_e_sucesso_vazio(monkeypatch):
    mock_auth(monkeypatch)
    monkeypatch.setattr(collectors.requests, "get", lambda url, **kw: response([] if url.endswith("/estacoes") else {}))
    with pytest.raises(RuntimeError, match="resposta"):
        collector().fetch(now=FIM)


def test_96_registros_com_lacuna_nao_sao_serie_completa():
    rows = [leitura(FIM - timedelta(minutes=14*i)) for i in range(96)]
    df = collector().process(payload(rows))
    assert df.iloc[0]["Prec_mm"] == 19.2
    assert "parcial" in df.iloc[0]["Observação"]


def test_estacao_com_apenas_dados_antigos_nao_aparece_com_chuva_zero():
    df = collector().process(payload([leitura(INICIO - timedelta(days=1), 20)]))
    assert df.empty
    assert "0/96" in str(df.attrs["avisos"])


def test_falha_em_uma_estacao_preserva_resultado_de_outra(monkeypatch):
    mock_auth(monkeypatch)
    def get(url, **kw):
        if url.endswith("/estacoes"):
            return response([])
        if kw["params"]["estacao"] == "EMA_VAR_P_01":
            return response({}, 500)
        return response({"items": [leitura(FIM, 3)], "next_cursor": None})
    monkeypatch.setattr(collectors.requests, "get", get)
    df = collector(estacoes_dict={"EMA_ADN_01": "ÁGUA DOCE DO NORTE", "EMA_VAR_P_01": "VARGEM ALTA"}).fetch(now=FIM)
    assert len(df) == 1
    assert df.iloc[0]["Prec_mm"] == 3
    assert "EMA_VAR_P_01" in str(df.attrs["avisos"])
    assert "HTTP 500" in str(df.attrs["avisos"])
