import pandas as pd
import pytest
import requests

from app import main
from app.services.normalizacao import garantir_colunas_estendidas


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    def bloquear(*args, **kwargs):
        raise AssertionError("Teste de integração não deve acessar a rede")
    monkeypatch.setattr(requests, "get", bloquear)
    monkeypatch.setattr(requests, "post", bloquear)


def parcial():
    df = garantir_colunas_estendidas(pd.DataFrame([{
        "Município": "VARGEM ALTA", "Prec_mm": 2, "Instituição": "CEPDEC",
        "Estação": "EMA_VAR_P_01", "Observação": "Acumulado parcial: 80/96 leituras",
    }]))
    df.attrs["avisos"] = ["EMA_VAR_P_01: Acumulado parcial: 80/96 leituras"]
    return df


def test_coletar_fonte_preserva_soma_e_status_parcial():
    df, status = main.coletar_fonte("CEPDEC", parcial)
    assert df.iloc[0]["Prec_mm"] == 2
    assert status.to_dict()["Status"] == "Parcial"
    assert "80/96" in status.mensagem


def test_sem_leituras_nao_e_ok_nem_zero_de_chuva():
    df = main.dataframe_vazio()
    df.attrs["avisos"] = ["EMA_VAR_P_01: sem leituras nas últimas 24h"]
    _, status = main.coletar_fonte("CEPDEC", lambda: df)
    assert status.to_dict()["Status"] == "Parcial"
    assert status.registros == 0
    assert "sem leituras" in status.mensagem


def test_fonte_sem_avisos_continua_ok():
    df = parcial()
    df.attrs.clear()
    _, status = main.coletar_fonte("PMVV", lambda: df)
    assert status.to_dict()["Status"] == "OK"


def test_listas_identificam_acumulado_parcial(monkeypatch):
    linhas = []
    monkeypatch.setattr(main.st, "text", linhas.append)
    monkeypatch.setattr(main.st, "markdown", lambda *args, **kwargs: None)
    main.render_lista(parcial())
    main.render_lista_geral(parcial())
    assert len(linhas) == 2
    assert all("80/96" in linha and "2.00 mm" in linha for linha in linhas)


def test_carregar_acumulados_integra_secrets_e_avisos_cepdec(monkeypatch):
    config = {"client_id": "id", "client_secret": "secret", "x_api_key": "key",
              "grant_type": "client_credentials"}
    monkeypatch.setattr(main, "get_secret", lambda name, default=None: config.get(name, default))
    monkeypatch.setattr(main, "load_cemaden", main.dataframe_vazio)
    chamadas = []
    def load(*args):
        chamadas.append(args)
        return parcial()
    monkeypatch.setattr(main, "load_cepdec", load, raising=False)
    monkeypatch.setattr(main, "salvar_snapshot_json", lambda df: None)
    df, geral, status = main.carregar_acumulados()
    assert chamadas == [(main.CEPDEC_BASE_URL, main.CEPDEC_TOKEN_URL, "id", "secret", "key", "client_credentials")]
    assert len(df) == len(geral) == 1
    assert df.iloc[0]["Observação"]
    cepdec = next(s for s in status if s.fonte == "CEPDEC")
    assert cepdec.to_dict()["Status"] == "Parcial"


def test_cepdec_sem_configuracao_informa_falha(monkeypatch):
    monkeypatch.setattr(main, "get_secret", lambda name, default=None: default)
    monkeypatch.setattr(main, "load_cemaden", main.dataframe_vazio)
    monkeypatch.setattr(main, "salvar_snapshot_json", lambda df: None)
    _, _, status = main.carregar_acumulados()
    cepdec = next(s for s in status if s.fonte == "CEPDEC")
    assert cepdec.to_dict()["Status"] == "Falha"
    assert "configuradas" in cepdec.mensagem


def test_cache_cepdec_preserva_avisos_sem_refazer_consulta(monkeypatch):
    import json
    from datetime import datetime, timezone

    chamadas = []
    def response(body):
        r = requests.Response()
        r.status_code = 200
        r._content = json.dumps(body).encode()
        return r
    def post(*args, **kwargs):
        chamadas.append("token")
        return response({"access_token": "token"})
    def get(url, **kwargs):
        if url.endswith("/estacoes"):
            return response([])
        codigo = kwargs["params"]["estacao"]
        return response({"items": [{
            "estacao_codigo": codigo, "data_hora_utc": datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat(),
            "intervalo_minutos": 15, "qualidade": "VALIDO", "flags": [],
            "dados": {"PRECIPITACAO_MM": 1},
        }], "next_cursor": None})
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    main.load_cepdec.clear()
    try:
        args = ("https://simet.example", "https://auth.example", "id", "secret", "key", "client_credentials")
        primeiro = main.load_cepdec(*args)
        segundo = main.load_cepdec(*args)
        assert len(segundo) == 29
        assert "EMA_VAR_P_01" in segundo["Estação"].values
        assert segundo.attrs["avisos"] == primeiro.attrs["avisos"]
        assert len(segundo.attrs["avisos"]) == 29
        assert chamadas == ["token"]
    finally:
        main.load_cepdec.clear()


def test_ranking_e_mapa_mostram_aviso(monkeypatch):
    tabelas, mapas = [], []
    monkeypatch.setattr(main.st, "subheader", lambda *args: None)
    monkeypatch.setattr(main.st, "multiselect", lambda label, options, **kwargs: options)
    monkeypatch.setattr(main.st, "text_input", lambda *args: "")
    monkeypatch.setattr(main.st, "dataframe", lambda df, **kwargs: tabelas.append(df))
    monkeypatch.setattr(main, "st_folium", lambda mapa, **kwargs: mapas.append(mapa))
    main.render_ranking(parcial())
    main.render_mapa(parcial())
    assert "80/96" in tabelas[0].iloc[0]["Observação"]
    assert "80/96" in mapas[0].get_root().render()
