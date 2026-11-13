from __future__ import annotations

import json
from pathlib import Path

from app.config.settings import DATA_DIR


def carregar_base_estacoes(
    caminho: Path = DATA_DIR / "stations_ana_inmet.json",
) -> dict[str, dict]:
    """Metadados locais de ANA/INMET, independentes da coleta meteorológica."""
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))
