import pandas as pd

from app.services.normalizacao import garantir_colunas_estendidas, normalizar_municipio, to_float


def test_normalizar_municipio_remove_espacos_e_aplica_caixa_alta():
    assert normalizar_municipio("  Vila Velha  ") == "VILA VELHA"


def test_to_float_aceita_virgula_decimal():
    assert to_float("12,5") == 12.5


def test_garantir_colunas_estendidas_completa_contrato():
    df = pd.DataFrame(
        [{"Município": "Vitória", "Prec_mm": "8,2", "Instituição": "cemaden"}]
    )

    resultado = garantir_colunas_estendidas(df)

    assert resultado.loc[0, "Município"] == "VITÓRIA"
    assert resultado.loc[0, "Prec_mm"] == 8.2
    assert "Latitude" in resultado.columns
    assert "DataHoraReferencia" in resultado.columns
