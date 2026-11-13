from datetime import datetime, timezone

from app.dataCollector import AnaCollector, InmetCollector, PmvvCollector


def test_ana_preserva_metadados_locais_apos_migracao_de_fonte():
    collector = AnaCollector("id", "senha", {"57739000": "GUAÇUÍ"})
    meta = collector.base_estacoes["57739000"]
    assert meta["municipio"] == "GUAÇUÍ"
    assert meta["latitude"] == -20.7725
    assert meta["longitude"] == -41.6808


def test_inmet_preserva_metadados_locais_apos_migracao_de_fonte():
    collector = InmetCollector("token", {"A612": "VITÓRIA"})
    meta = collector.base_estacoes["A612"]
    assert meta["municipio"] == "VITÓRIA"
    assert meta["latitude"] == -20.27083332
    assert meta["altitude"] == 9


def test_inmet_extrai_chuva_de_payload_horario():
    item = {"CHUVA": "4.6", "DT_MEDICAO": "2026-06-27", "HR_MEDICAO": "1200"}

    assert InmetCollector._valor_chuva(item) == 4.6
    assert InmetCollector._timestamp_medicao(item) == datetime(
        2026, 6, 27, 12, 0, tzinfo=timezone.utc
    )


def test_pmvv_identifica_sensores_de_chuva_em_mm():
    dispositivo = {
        "sensorList": [
            {"id": 8, "name": "Temperatura", "unit": "ºC"},
            {"id": 35, "name": "Chuva", "unit": "mm"},
            {"id": 191, "name": "Chuva adicional", "unit": "mm"},
        ]
    }

    sensores = PmvvCollector._sensores_chuva(dispositivo)

    assert [sensor["id"] for sensor in sensores] == [35, 191]


def test_pmvv_valor_leitura_sensor_usa_value_formatted():
    assert PmvvCollector._valor_leitura_sensor({"valueFormatted": "2,4"}) == 2.4
