from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):
        return False


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"

load_dotenv(BASE_DIR / ".env")


def get_env(name: str, default: str | None = None) -> str | None:
    """Lê variável do ambiente/.env sem expor o valor em logs."""
    return os.getenv(name, default)


APP_TITLE = "Acumulados de Chuva nas Últimas 24h — Espírito Santo"
APP_SUBTITLE = (
    "Script para verificação dos maiores acumulados de chuva de cada município "
    "do ES no período de 24h"
)

CACHE_TTL_SECONDS = 120
REQUEST_TIMEOUT_SECONDS = 30
ANA_TOKEN_TTL_SECONDS = 900

CEMADEN_URL = "https://resources.cemaden.gov.br/graficos/interativo/getJson2.php?uf=ES"
ANA_BASE_URL = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"
ANA_TOKEN_URL = f"{ANA_BASE_URL}/OAUth/v1"
INMET_BASE_URL = "https://apitempo.inmet.gov.br"
PMVV_BASE_URL = "https://prod-api.plugfield.com.br"
CEPDEC_BASE_URL = "https://sistemas.cb.es.gov.br/simet-api"
CEPDEC_TOKEN_URL = (
    "https://sistemas.cb.es.gov.br/keycloak/realms/sistemas-cepdec/"
    "protocol/openid-connect/token"
)

SOURCE_CEMADEN = "CEMADEN"
SOURCE_CEPDEC = "CEPDEC"
SOURCE_ANA = "ANA"
SOURCE_INMET = "INMET"
SOURCE_PMVV = "PMVV"

BASE_COLUMNS = ["Município", "Prec_mm", "Instituição"]

EXTENDED_COLUMNS = [
    "Município",
    "Prec_mm",
    "Instituição",
    "Estação",
    "Latitude",
    "Longitude",
    "Altitude",
    "DataHoraReferencia",
    "Fonte",
    "Observação",
]
