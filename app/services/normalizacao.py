from __future__ import annotations

import unicodedata
from typing import Any

import pandas as pd

from app.config.settings import EXTENDED_COLUMNS


def remover_acentos(valor: str) -> str:
    normalizado = unicodedata.normalize("NFKD", valor)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def normalizar_texto(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    texto = " ".join(texto.split())
    return texto


def normalizar_municipio(valor: Any) -> str:
    texto = normalizar_texto(valor)
    if not texto:
        return ""
    return texto.upper()


def normalizar_instituicao(valor: Any) -> str:
    texto = normalizar_texto(valor)
    if not texto:
        return ""
    return remover_acentos(texto).upper()


def to_float(valor: Any, default: float = 0.0) -> float:
    if valor in (None, ""):
        return default

    if isinstance(valor, str):
        valor = valor.replace(",", ".")

    try:
        return float(valor)
    except (TypeError, ValueError):
        return default


def garantir_colunas_estendidas(df: pd.DataFrame) -> pd.DataFrame:
    resultado = df.copy()
    for coluna in EXTENDED_COLUMNS:
        if coluna not in resultado.columns:
            resultado[coluna] = None

    if "Município" in resultado.columns:
        resultado["Município"] = resultado["Município"].map(normalizar_municipio)

    if "Instituição" in resultado.columns:
        resultado["Instituição"] = resultado["Instituição"].map(normalizar_instituicao)

    if "Fonte" in resultado.columns:
        resultado["Fonte"] = resultado["Fonte"].fillna(resultado["Instituição"])

    if "Prec_mm" in resultado.columns:
        resultado["Prec_mm"] = resultado["Prec_mm"].map(to_float).round(2)

    return resultado[EXTENDED_COLUMNS]
