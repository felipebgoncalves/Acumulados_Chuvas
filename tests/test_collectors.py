from datetime import datetime, timezone

from app.dataCollector import InmetCollector, SatdesCollector


def test_inmet_extrai_chuva_de_payload_horario():
    item = {"CHUVA": "4.6", "DT_MEDICAO": "2026-06-27", "HR_MEDICAO": "1200"}

    assert InmetCollector._valor_chuva(item) == 4.6
    assert InmetCollector._timestamp_medicao(item) == datetime(
        2026, 6, 27, 12, 0, tzinfo=timezone.utc
    )


def test_satdes_filtra_inmet_e_ana_do_payload():
    payload = (
        {
            "data": {
                "prec": {
                    "grupo": [
                        {
                            "id_station": 1,
                            "name": "EMA_SER_01",
                            "code": "CEP_001_A",
                            "date_utc": "2026-06-27T12:00:00Z",
                            "instant": "3.2",
                        },
                        {
                            "id_station": 2,
                            "name": "A612",
                            "code": "INMET_001_A",
                            "date_utc": "2026-06-27T12:00:00Z",
                            "instant": "9.9",
                        },
                    ]
                }
            }
        },
        datetime(2026, 6, 27, 11, 0, tzinfo=timezone.utc),
        datetime(2026, 6, 27, 13, 0, tzinfo=timezone.utc),
    )

    resultado = SatdesCollector().process(payload)

    assert len(resultado) == 1
    assert resultado.loc[0, "Instituição"] == "CEPDEC"
