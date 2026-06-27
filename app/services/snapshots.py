from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from app.config.settings import SNAPSHOT_DIR


TZ_BRT = ZoneInfo("America/Sao_Paulo")


def salvar_snapshot_json(df: pd.DataFrame) -> str | None:
    """Salva snapshot JSON dos acumulados. Falhas não devem interromper o app."""
    if df is None or df.empty:
        return None

    try:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        agora = datetime.now(TZ_BRT)
        payload = {
            "gerado_em": agora.isoformat(),
            "registros": df.to_dict(orient="records"),
        }

        nome_arquivo = f"acumulados_{agora.strftime('%Y%m%d_%H%M%S')}.json"
        caminho = SNAPSHOT_DIR / nome_arquivo
        caminho.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        latest = SNAPSHOT_DIR / "acumulados_latest.json"
        latest.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(caminho)
    except Exception:
        return None
