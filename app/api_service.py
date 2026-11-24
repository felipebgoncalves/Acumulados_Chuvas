"""Coleta e contrato JSON da interface FastAPI, sem dependência de Streamlit."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock, Thread
from time import monotonic, perf_counter
from zoneinfo import ZoneInfo

import pandas as pd

from app.codEstacoes import ANA, INMET
from app.config.settings import (
    CACHE_TTL_SECONDS,
    CEPDEC_BASE_URL,
    CEPDEC_TOKEN_URL,
    EXTENDED_COLUMNS,
    PMVV_BASE_URL,
    SOURCE_ANA,
    SOURCE_CEMADEN,
    SOURCE_CEPDEC,
    SOURCE_INMET,
    SOURCE_PMVV,
    get_env,
)
from app.dataCollector import (
    AnaCollector,
    CemadenCollector,
    CepdecCollector,
    InmetCollector,
    Joiner,
    PmvvCollector,
)
from app.municipiosES import COORDENADAS_ESPIRITO_SANTO
from app.services.fonte_status import FonteStatus
from app.services.snapshots import salvar_snapshot_json

TZ_BRT = ZoneInfo("America/Sao_Paulo")


def empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=EXTENDED_COLUMNS)


def _collect_one(name: str, fetch):
    started = perf_counter()
    try:
        frame = fetch()
        if frame is None:
            frame = empty_frame()
        status = FonteStatus.sucesso_coleta(name, len(frame), perf_counter() - started)
        warnings = frame.attrs.get("avisos", [])
        if warnings:
            status.parcial = True
            status.mensagem = " | ".join(warnings)
        return frame, status
    except Exception as exc:
        return empty_frame(), FonteStatus.falha_coleta(name, exc, perf_counter() - started)


def _sources():
    tasks = [(SOURCE_CEMADEN, lambda: CemadenCollector().get_dataframe())]
    missing = []

    client_id = get_env("client_id")
    client_secret = get_env("client_secret")
    api_key = get_env("x-api-key") or get_env("x_api_key")
    if all((client_id, client_secret, api_key)):
        tasks.append((SOURCE_CEPDEC, lambda: CepdecCollector(
            base_url=CEPDEC_BASE_URL,
            token_url=CEPDEC_TOKEN_URL,
            client_id=client_id,
            client_secret=client_secret,
            api_key=api_key,
            grant_type=get_env("grant_type", "client_credentials"),
        ).fetch()))
    else:
        missing.append(SOURCE_CEPDEC)

    ana_id, ana_pwd = get_env("ANA_ID"), get_env("ANA_PWD")
    if ana_id and ana_pwd:
        tasks.append((SOURCE_ANA, lambda: AnaCollector(
            identificador=ana_id, senha=ana_pwd, estacoes_dict=ANA, max_workers=8,
        ).fetch()))
    else:
        missing.append(SOURCE_ANA)

    inmet_token = get_env("INMET_API_TOKEN")
    if inmet_token:
        tasks.append((SOURCE_INMET, lambda: InmetCollector(
            token=inmet_token, estacoes_dict=INMET, max_workers=8,
        ).fetch()))
    else:
        missing.append(SOURCE_INMET)

    pmvv_key = get_env("PMVV_API_Key")
    pmvv_user = get_env("PMVV_Username")
    pmvv_password = get_env("PMVV_PASSWORD")
    if all((pmvv_key, pmvv_user, pmvv_password)):
        tasks.append((SOURCE_PMVV, lambda: PmvvCollector(
            api_key=pmvv_key,
            username=pmvv_user,
            password=pmvv_password,
            base_url=PMVV_BASE_URL,
            max_workers=8,
        ).fetch()))
    else:
        missing.append(SOURCE_PMVV)
    return tasks, missing


def _json_value(value):
    if value is None:
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return value.item() if hasattr(value, "item") else value
    if pd.isna(value):
        return None
    return value


def _records(frame: pd.DataFrame) -> list[dict]:
    records = []
    for row in frame.to_dict(orient="records"):
        item = {key: _json_value(value) for key, value in row.items()}
        coords = COORDENADAS_ESPIRITO_SANTO.get(item.get("Município"))
        if coords:
            item["Latitude"] = item["Latitude"] if item.get("Latitude") is not None else coords[0]
            item["Longitude"] = item["Longitude"] if item.get("Longitude") is not None else coords[1]
        records.append(item)
    return records


def collect_dashboard() -> dict:
    tasks, missing = _sources()
    results = {}
    with ThreadPoolExecutor(max_workers=min(len(tasks), 5) or 1) as pool:
        futures = {pool.submit(_collect_one, name, fetch): name for name, fetch in tasks}
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    frames = [results[name][0] for name, _ in tasks]
    statuses = [results[name][1] for name, _ in tasks]
    statuses += [FonteStatus.falha_coleta(name, "Credenciais não configuradas.") for name in missing]
    all_records = Joiner.all_records(*frames)
    consolidated = Joiner.join(*frames)
    salvar_snapshot_json(consolidated)
    main_records = _records(consolidated)
    return {
        "updated_at": datetime.now(TZ_BRT).isoformat(),
        "summary": {
            "maximum_mm": max((row["Prec_mm"] for row in main_records), default=0),
            "top_city": main_records[0]["Município"] if main_records else None,
            "rainy_cities": len(main_records),
            "active_sources": sum(status.sucesso for status in statuses),
        },
        "ranking": main_records,
        "general": _records(all_records)[:60],
        "sources": [status.to_dict() for status in statuses],
    }


class DashboardCache:
    """Mantém o último resultado visível enquanto atualiza em segundo plano."""

    def __init__(self, collect=collect_dashboard, ttl_seconds=CACHE_TTL_SECONDS):
        self.collect = collect
        self.ttl_seconds = ttl_seconds
        self._lock = Lock()
        self._payload = None
        self._fetched_at = 0.0
        self._loading = False
        self._error = None

    def _refresh(self):
        try:
            payload = self.collect()
            with self._lock:
                self._payload = payload
                self._fetched_at = monotonic()
                self._error = None
        except Exception as exc:
            with self._lock:
                self._error = f"Falha na consolidação: {exc.__class__.__name__}"
                self._fetched_at = monotonic()
        finally:
            with self._lock:
                self._loading = False

    def get(self, force=False):
        with self._lock:
            stale = monotonic() - self._fetched_at >= self.ttl_seconds
            if (force or stale or self._payload is None) and not self._loading:
                self._loading = True
                Thread(target=self._refresh, daemon=True).start()
            return {
                "loading": self._loading,
                "error": self._error,
                "data": self._payload,
            }
