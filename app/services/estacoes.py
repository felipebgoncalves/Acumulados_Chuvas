from __future__ import annotations

import json
from pathlib import Path

import requests

from app.config.settings import (
    REQUEST_TIMEOUT_SECONDS,
    SATDES_STATIONS_FILE,
    SATDES_STATIONS_URL,
)
from app.services.normalizacao import normalizar_instituicao, normalizar_municipio


def carregar_base_estacoes(caminho: Path = SATDES_STATIONS_FILE) -> dict[str, dict]:
    if not caminho.exists():
        return {}

    payload = json.loads(caminho.read_text(encoding="utf-8-sig"))
    registros = payload.get("data", payload if isinstance(payload, list) else [])

    base = {}
    for item in registros:
        nome = item.get("name")
        if not nome:
            continue

        base[nome] = {
            "estacao": nome,
            "codigo": item.get("code"),
            "municipio": normalizar_municipio(item.get("name_county")),
            "instituicao": normalizar_instituicao(item.get("name_institute")),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "altitude": item.get("altitude"),
            "tipo": item.get("type"),
            "ativa": item.get("active"),
        }

    return base


def atualizar_base_estacoes(caminho: Path = SATDES_STATIONS_FILE) -> int:
    response = requests.get(SATDES_STATIONS_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return len(payload.get("data", []))
