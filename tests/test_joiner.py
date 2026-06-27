import pandas as pd

from app.dataCollector import Joiner


def test_joiner_mantem_maior_acumulado_por_municipio():
    df_1 = pd.DataFrame(
        [
            {"Município": "VITÓRIA", "Prec_mm": 5.0, "Instituição": "CEMADEN"},
            {"Município": "SERRA", "Prec_mm": 12.0, "Instituição": "CEMADEN"},
        ]
    )
    df_2 = pd.DataFrame(
        [
            {"Município": "VITÓRIA", "Prec_mm": 18.0, "Instituição": "INMET"},
            {"Município": "SERRA", "Prec_mm": 3.0, "Instituição": "SATDES"},
        ]
    )

    resultado = Joiner.join(df_1, df_2)

    vitoria = resultado.loc[resultado["Município"] == "VITÓRIA"].iloc[0]
    serra = resultado.loc[resultado["Município"] == "SERRA"].iloc[0]

    assert vitoria["Prec_mm"] == 18.0
    assert vitoria["Instituição"] == "INMET"
    assert serra["Prec_mm"] == 12.0
    assert serra["Instituição"] == "CEMADEN"


def test_joiner_ignora_valores_zerados_e_negativos():
    df = pd.DataFrame(
        [
            {"Município": "VITÓRIA", "Prec_mm": 0.0, "Instituição": "CEMADEN"},
            {"Município": "SERRA", "Prec_mm": -1.0, "Instituição": "ANA"},
        ]
    )

    resultado = Joiner.join(df)

    assert resultado.empty
