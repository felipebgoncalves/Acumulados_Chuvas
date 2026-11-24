from time import sleep

import pandas as pd

from app import api_service
from app.services.fonte_status import FonteStatus


def test_collect_dashboard_keeps_all_records_and_highest_city(monkeypatch):
    frame = pd.DataFrame([
        {"Município": "VILA VELHA", "Prec_mm": 3.0, "Instituição": "CEPDEC"},
        {"Município": "VILA VELHA", "Prec_mm": 2.0, "Instituição": "CEPDEC"},
        {"Município": "SERRA", "Prec_mm": 1.0, "Instituição": "CEPDEC"},
    ])
    monkeypatch.setattr(api_service, "_sources", lambda: ([("CEPDEC", lambda: frame)], ["ANA"]))
    monkeypatch.setattr(api_service, "salvar_snapshot_json", lambda _: None)

    payload = api_service.collect_dashboard()

    assert len(payload["ranking"]) == 2
    assert len(payload["general"]) == 3
    assert payload["summary"]["maximum_mm"] == 3.0
    assert payload["summary"]["active_sources"] == 1
    assert payload["ranking"][0]["Latitude"] is not None
    assert payload["sources"][1]["Status"] == "Falha"


def test_dashboard_cache_returns_immediately_and_preserves_previous_data():
    calls = []

    def collect():
        calls.append(True)
        sleep(0.05)
        return {"ranking": [1]}

    cache = api_service.DashboardCache(collect=collect, ttl_seconds=120)
    first = cache.get()
    assert first["loading"] is True
    assert first["data"] is None
    for _ in range(50):
        if not cache.get()["loading"]:
            break
        sleep(0.01)
    assert cache.get()["data"] == {"ranking": [1]}
    assert len(calls) == 1


def test_json_value_replaces_missing_values():
    assert api_service._json_value(float("nan")) is None
    assert api_service._json_value(pd.NA) is None
