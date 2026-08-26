from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import urllib3
from dateutil.parser import parse

try:
    import streamlit as st
except ModuleNotFoundError:
    class _StreamlitFallback:
        @staticmethod
        def cache_resource(*args, **kwargs):
            def decorator(func):
                return func

            return decorator

    st = _StreamlitFallback()

from app.codEstacoes import ANA, CEPDEC, INCAPER, INMET
from app.config.settings import (
    ALLOWED_SATDES_INSTITUTIONS,
    ANA_BASE_URL,
    ANA_TOKEN_TTL_SECONDS,
    ANA_TOKEN_URL,
    CEMADEN_URL,
    EXTENDED_COLUMNS,
    INMET_BASE_URL,
    PMVV_BASE_URL,
    REQUEST_TIMEOUT_SECONDS,
    SATDES_MAP_URL,
    SOURCE_ANA,
    SOURCE_CEMADEN,
    SOURCE_INMET,
    SOURCE_PMVV,
)
from app.services.estacoes import carregar_base_estacoes
from app.services.normalizacao import (
    garantir_colunas_estendidas,
    normalizar_instituicao,
    to_float,
)

urllib3.disable_warnings()

TZ_BRT = ZoneInfo("America/Sao_Paulo")


def erro_http_resumido(exc: Exception) -> str:
    """Formata erros HTTP sem expor URL, tokens ou parâmetros sensíveis."""
    response = getattr(exc, "response", None)
    if response is not None:
        return f"HTTP {response.status_code}"

    return exc.__class__.__name__


MAPA_ESTACOES_SATDES = {
    **{k: ("CEPDEC", v) for k, v in CEPDEC.items()},
    **{k: ("INCAPER", v) for k, v in INCAPER.items()},
}


class DataCollector:
    """Classe base para todos os coletores de acumulados."""

    fonte = "DESCONHECIDA"

    def fetch(self):
        raise NotImplementedError("Implementar fetch() na classe filha.")

    def process(self, data):
        raise NotImplementedError("Implementar process() na classe filha.")

    def get_dataframe(self):
        data = self.fetch()
        return self.process(data)

    @staticmethod
    def empty_dataframe() -> pd.DataFrame:
        return pd.DataFrame(columns=EXTENDED_COLUMNS)

    @staticmethod
    def finalize(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return DataCollector.empty_dataframe()
        return garantir_colunas_estendidas(df)


class CemadenCollector(DataCollector):
    fonte = SOURCE_CEMADEN
    BASE_URL = CEMADEN_URL

    def fetch(self):
        headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
        response = requests.get(
            self.BASE_URL,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            verify=False,
        )
        response.raise_for_status()
        return response.json()

    def process(self, data):
        df = pd.DataFrame(data)

        if df.empty:
            return self.empty_dataframe()

        df = (
            df[df["acc24hr"] != "-"]
            .assign(acc24hr=lambda x: x["acc24hr"].map(to_float))
            .query("acc24hr >= 0")
            .groupby("cidade", as_index=False)["acc24hr"]
            .max()
            .rename(columns={"cidade": "Município", "acc24hr": "Prec_mm"})
        )

        df["Instituição"] = SOURCE_CEMADEN
        df["Fonte"] = SOURCE_CEMADEN
        df["DataHoraReferencia"] = datetime.now(TZ_BRT).isoformat()
        return self.finalize(df)


class SatdesCollector(DataCollector):
    fonte = "SATDES"
    BASE_URL = SATDES_MAP_URL

    def __init__(self):
        self.base_estacoes = carregar_base_estacoes()

    def fetch(self):
        end_utc = datetime.now(timezone.utc)
        start_utc = end_utc - timedelta(hours=24)
        inicio = start_utc.strftime("%Y-%m-%dT%H:%M")
        fim = end_utc.strftime("%Y-%m-%dT%H:%M")
        url = f"{self.BASE_URL}/{inicio}/{fim}"

        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json(), start_utc, end_utc

    def _metadados_estacao(self, nome: str) -> dict:
        return self.base_estacoes.get(nome, {})

    def process(self, payload):
        data, start_utc, end_utc = payload
        registros = []

        for lista in data.get("data", {}).get("prec", {}).values():
            for item in lista:
                nome = item.get("name")
                codigo = item.get("code", "")
                metadados = self._metadados_estacao(nome)

                instituicao = normalizar_instituicao(
                    metadados.get("instituicao")
                    or MAPA_ESTACOES_SATDES.get(nome, ("DESCONHECIDA", nome))[0]
                )

                if instituicao not in ALLOWED_SATDES_INSTITUTIONS:
                    continue

                if "ANA" in codigo or "INMET" in codigo:
                    continue

                date_utc = item.get("date_utc")
                if not date_utc:
                    continue

                ts_utc = datetime.fromisoformat(date_utc.replace("Z", "+00:00"))
                if not (start_utc <= ts_utc <= end_utc):
                    continue

                municipio = (
                    metadados.get("municipio")
                    or MAPA_ESTACOES_SATDES.get(nome, ("DESCONHECIDA", nome))[1]
                )

                registros.append(
                    {
                        "id_estacao": item.get("id_station"),
                        "Município": municipio,
                        "Instituição": instituicao,
                        "Prec_mm": to_float(item.get("instant")),
                        "Estação": nome,
                        "Latitude": metadados.get("latitude"),
                        "Longitude": metadados.get("longitude"),
                        "Altitude": metadados.get("altitude"),
                        "DataHoraReferencia": ts_utc.astimezone(TZ_BRT).isoformat(),
                        "Fonte": "SATDES",
                    }
                )

        df = pd.DataFrame(registros)
        if df.empty:
            return self.empty_dataframe()

        agrupado = (
            df.groupby(
                [
                    "id_estacao",
                    "Município",
                    "Instituição",
                    "Estação",
                    "Latitude",
                    "Longitude",
                    "Altitude",
                    "Fonte",
                ],
                dropna=False,
                as_index=False,
            )
            .agg(
                Prec_mm=("Prec_mm", "sum"),
                DataHoraReferencia=("DataHoraReferencia", "max"),
            )
        )

        agrupado = agrupado[agrupado["Prec_mm"] > 0]
        return self.finalize(agrupado)


@st.cache_resource(ttl=ANA_TOKEN_TTL_SECONDS)
def obter_token_ana(identificador: str, senha: str) -> str:
    """Obtém e mantém em cache o token da ANA."""
    headers = {
        "Identificador": identificador,
        "Senha": senha,
    }

    response = requests.get(ANA_TOKEN_URL, headers=headers, timeout=90)
    response.raise_for_status()

    token = response.json().get("items", {}).get("tokenautenticacao")
    if not token:
        raise RuntimeError("Token ANA não retornado pela API.")

    return token


class AnaCollector(DataCollector):
    fonte = SOURCE_ANA
    BASE_URL = ANA_BASE_URL

    def __init__(self, identificador, senha, estacoes_dict, max_workers=8):
        self.identificador = identificador
        self.senha = senha
        self.estacoes = estacoes_dict
        self.max_workers = max_workers
        self.base_estacoes = carregar_base_estacoes()

    def _consulta_estacao(self, codigo, token):
        data_busca = datetime.now(TZ_BRT).strftime("%Y-%m-%d")
        url = (
            f"{self.BASE_URL}/HidroinfoanaSerieTelemetricaAdotada/v1"
            f"?Código da Estação={codigo}"
            f"&Tipo Filtro Data=DATA_LEITURA"
            f"&Data de Busca (yyyy-MM-dd)={data_busca}"
            f"&Range Intervalo de busca=DIAS_2"
        )

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return codigo, response.json()

    def fetch(self):
        end_utc = datetime.now(timezone.utc)
        start_utc = end_utc - timedelta(hours=24)
        registros = []

        token = obter_token_ana(self.identificador, self.senha)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._consulta_estacao, cod, token): (cod, muni)
                for cod, muni in self.estacoes.items()
            }

            for future in as_completed(futures):
                cod, muni = futures[future]
                metadados = self.base_estacoes.get(cod, {})

                try:
                    _, payload = future.result()
                    items = payload.get("items", [])
                    soma = 0.0
                    ultima_referencia = None

                    for item in items:
                        data_str = item.get("Data_Hora_Medicao")
                        if not data_str:
                            continue

                        try:
                            ts = parse(data_str)
                            ts = ts.replace(tzinfo=TZ_BRT).astimezone(timezone.utc)
                        except Exception:
                            continue

                        if not (start_utc <= ts <= end_utc):
                            continue

                        soma += to_float(item.get("Chuva_Adotada"))
                        ultima_referencia = ts.astimezone(TZ_BRT).isoformat()

                    if soma > 0:
                        registros.append(
                            {
                                "Estação": cod,
                                "Município": metadados.get("municipio") or muni,
                                "Instituição": SOURCE_ANA,
                                "Prec_mm": round(soma, 2),
                                "Latitude": metadados.get("latitude"),
                                "Longitude": metadados.get("longitude"),
                                "Altitude": metadados.get("altitude"),
                                "DataHoraReferencia": ultima_referencia,
                                "Fonte": SOURCE_ANA,
                            }
                        )
                except Exception as exc:
                    print(f"Erro na estação ANA {cod}: {erro_http_resumido(exc)}")

        if not registros:
            return self.empty_dataframe()

        df = pd.DataFrame(registros).sort_values(by="Prec_mm", ascending=False)
        return self.finalize(df)


class InmetCollector(DataCollector):
    fonte = SOURCE_INMET
    BASE_URL = INMET_BASE_URL

    def __init__(self, token: str, estacoes_dict=None, max_workers=8):
        self.token = token
        self.estacoes = estacoes_dict or INMET
        self.max_workers = max_workers
        self.base_estacoes = carregar_base_estacoes()

    def _consulta_estacao(self, codigo: str):
        fim = datetime.now(TZ_BRT).date()
        inicio = fim - timedelta(days=1)
        url = (
            f"{self.BASE_URL}/token/estacao/"
            f"{inicio.isoformat()}/{fim.isoformat()}/{codigo}/{self.token}"
        )

        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return codigo, response.json()

    @staticmethod
    def _valor_chuva(item: dict) -> float:
        for chave in ("CHUVA", "chuva", "PRECIPITACAO", "PRECIPITAÇÃO", "precipitacao"):
            if chave in item:
                return to_float(item.get(chave))
        return 0.0

    @staticmethod
    def _timestamp_medicao(item: dict):
        data = item.get("DT_MEDICAO") or item.get("data") or item.get("Data")
        hora = item.get("HR_MEDICAO") or item.get("hora") or item.get("Hora") or "0000"

        if not data:
            return None

        hora = str(hora).zfill(4)[:4]
        try:
            return datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H%M").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            try:
                return parse(str(data)).replace(tzinfo=timezone.utc)
            except Exception:
                return None

    def fetch(self):
        if not self.token:
            raise RuntimeError("Token INMET não configurado.")

        end_utc = datetime.now(timezone.utc)
        start_utc = end_utc - timedelta(hours=24)
        registros = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._consulta_estacao, cod): (cod, muni)
                for cod, muni in self.estacoes.items()
            }

            for future in as_completed(futures):
                cod, muni = futures[future]
                metadados = self.base_estacoes.get(cod, {})

                try:
                    _, payload = future.result()
                    if isinstance(payload, dict):
                        items = payload.get("data", payload.get("items", []))
                    else:
                        items = payload

                    soma = 0.0
                    ultima_referencia = None

                    for item in items or []:
                        ts = self._timestamp_medicao(item)
                        if not ts or not (start_utc <= ts <= end_utc):
                            continue

                        soma += self._valor_chuva(item)
                        ultima_referencia = ts.astimezone(TZ_BRT).isoformat()

                    if soma > 0:
                        registros.append(
                            {
                                "Estação": cod,
                                "Município": metadados.get("municipio") or muni,
                                "Instituição": SOURCE_INMET,
                                "Prec_mm": round(soma, 2),
                                "Latitude": metadados.get("latitude"),
                                "Longitude": metadados.get("longitude"),
                                "Altitude": metadados.get("altitude"),
                                "DataHoraReferencia": ultima_referencia,
                                "Fonte": SOURCE_INMET,
                            }
                        )
                except Exception as exc:
                    print(f"Erro na estação INMET {cod}: {erro_http_resumido(exc)}")

        if not registros:
            return self.empty_dataframe()

        df = pd.DataFrame(registros).sort_values(by="Prec_mm", ascending=False)
        return self.finalize(df)


class PmvvCollector(DataCollector):
    fonte = SOURCE_PMVV
    BASE_URL = PMVV_BASE_URL

    def __init__(
        self,
        api_key: str,
        username: str,
        password: str,
        base_url: str | None = None,
        max_workers: int = 8,
    ):
        self.api_key = api_key
        self.username = username
        self.password = password
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.max_workers = max_workers

    def _api_headers(self, token: str | None = None) -> dict:
        headers = {"x-api-key": self.api_key}
        if token:
            headers["authorization"] = token
        return headers

    def _login(self) -> str:
        payload = {"username": self.username, "password": self.password}
        response = requests.post(
            f"{self.base_url}/login",
            headers=self._api_headers(),
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        token = response.json().get("access_token")
        if not token:
            raise RuntimeError("Token PMVV não retornado pela API.")

        return token

    def _listar_dispositivos(self, token: str) -> list[dict]:
        dispositivos = []
        pagina = 1

        while True:
            response = requests.get(
                f"{self.base_url}/device",
                params={"page": pagina},
                headers=self._api_headers(token),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()

            lista = payload.get("deviceList") or payload.get("data", {}).get("deviceList") or []
            dispositivos.extend(lista)

            paginacao = payload.get("pagination") or {}
            total_paginas = (
                paginacao.get("totalPages")
                or paginacao.get("total_pages")
                or paginacao.get("pages")
            )

            if total_paginas and pagina < int(total_paginas):
                pagina += 1
                continue

            if not total_paginas and lista:
                pagina_atual = paginacao.get("page") or paginacao.get("currentPage")
                proxima = paginacao.get("nextPage") or paginacao.get("next")
                if proxima and pagina_atual != proxima:
                    pagina = int(proxima)
                    continue

            break

        return dispositivos

    @staticmethod
    def _periodo_24h() -> tuple[datetime, datetime, int, int]:
        fim = datetime.now(TZ_BRT)
        inicio = fim - timedelta(hours=24)
        return (
            inicio,
            fim,
            int(inicio.timestamp() * 1000),
            int(fim.timestamp() * 1000),
        )

    @staticmethod
    def _sensores_chuva(dispositivo: dict) -> list[dict]:
        sensores = []

        for sensor in dispositivo.get("sensorList") or []:
            nome = str(sensor.get("name") or "").lower()
            unidade = str(sensor.get("unit") or "").lower()

            if "chuva" in nome and unidade == "mm":
                sensores.append(sensor)

        return sensores

    def _consultar_sensor(
        self,
        device_id: int,
        sensor_id: int,
        token: str,
        inicio_ms: int,
        fim_ms: int,
    ):
        leituras = []
        pagina = 1

        while True:
            response = requests.get(
                f"{self.base_url}/data/sensor",
                params={
                    "device": device_id,
                    "sensor": sensor_id,
                    "time": inicio_ms,
                    "timeMax": fim_ms,
                    "page": pagina,
                },
                headers=self._api_headers(token),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()

            dados = payload.get("data", payload if isinstance(payload, list) else [])
            leituras.extend(dados or [])

            paginacao = payload.get("pagination") if isinstance(payload, dict) else {}
            total_paginas = (paginacao or {}).get("totalPages")

            if total_paginas and pagina < int(total_paginas):
                pagina += 1
                continue

            break

        return device_id, sensor_id, leituras

    @staticmethod
    def _valor_leitura_sensor(item: dict) -> float:
        return to_float(item.get("valueFormatted"))

    @staticmethod
    def _data_referencia(item: dict) -> str | None:
        timestamp = item.get("time") or item.get("timestamp")
        if timestamp:
            try:
                return datetime.fromtimestamp(
                    int(timestamp) / 1000,
                    tz=timezone.utc,
                ).astimezone(TZ_BRT).isoformat()
            except Exception:
                return None

        return None

    @staticmethod
    def _coordenada_dispositivo(dispositivo: dict, chave: str):
        return dispositivo.get(chave) or dispositivo.get("dashboard", {}).get(chave)

    def fetch(self):
        if not self.api_key or not self.username or not self.password:
            raise RuntimeError("Credenciais PMVV não configuradas.")

        token = self._login()
        dispositivos = self._listar_dispositivos(token)
        _, _, inicio_ms, fim_ms = self._periodo_24h()
        registros = []
        dispositivos_por_id = {item.get("id"): item for item in dispositivos if item.get("id")}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._consultar_sensor,
                    device_id,
                    sensor.get("id"),
                    token,
                    inicio_ms,
                    fim_ms,
                ): (device_id, sensor)
                for device_id, dispositivo in dispositivos_por_id.items()
                for sensor in self._sensores_chuva(dispositivo)
                if sensor.get("id")
            }

            acumulados_por_dispositivo = {}

            for future in as_completed(futures):
                device_id, sensor = futures[future]
                dispositivo = dispositivos_por_id[device_id]

                try:
                    _, sensor_id, leituras = future.result()
                    soma = 0.0
                    ultima_referencia = None

                    for item in leituras or []:
                        soma += self._valor_leitura_sensor(item)
                        ultima_referencia = self._data_referencia(item) or ultima_referencia

                    sensor_atual = acumulados_por_dispositivo.get(device_id)
                    if sensor_atual is None or soma > sensor_atual["soma"]:
                        acumulados_por_dispositivo[device_id] = {
                            "soma": soma,
                            "sensor_id": sensor_id,
                            "sensor_nome": sensor.get("name"),
                            "ultima_referencia": ultima_referencia,
                            "dispositivo": dispositivo,
                        }
                except Exception as exc:
                    print(
                        f"Erro na estação PMVV {device_id}, "
                        f"sensor {sensor.get('id')}: {erro_http_resumido(exc)}"
                    )

        for acumulado in acumulados_por_dispositivo.values():
            soma = acumulado["soma"]
            if soma <= 0:
                continue

            dispositivo = acumulado["dispositivo"]
            registros.append(
                {
                    "Município": "VILA VELHA",
                    "Prec_mm": round(soma, 2),
                    "Instituição": SOURCE_PMVV,
                    "Estação": (
                        f"{dispositivo.get('name') or dispositivo.get('id')} "
                        f"({acumulado['sensor_nome']})"
                    ),
                    "Latitude": self._coordenada_dispositivo(dispositivo, "latitude"),
                    "Longitude": self._coordenada_dispositivo(dispositivo, "longitude"),
                    "Altitude": dispositivo.get("altitude"),
                    "DataHoraReferencia": acumulado["ultima_referencia"],
                    "Fonte": SOURCE_PMVV,
                }
            )

        if not registros:
            return self.empty_dataframe()

        df = pd.DataFrame(registros).sort_values(by="Prec_mm", ascending=False)
        return self.finalize(df)


class Joiner:
    @staticmethod
    def all_records(*dfs):
        validos = [
            garantir_colunas_estendidas(df)
            for df in dfs
            if df is not None and not df.empty
        ]

        if not validos:
            return DataCollector.empty_dataframe()

        df = pd.concat(validos, ignore_index=True)
        df = df[df["Prec_mm"] > 0]

        if df.empty:
            return DataCollector.empty_dataframe()

        return df.sort_values("Prec_mm", ascending=False).reset_index(drop=True)

    @staticmethod
    def join(*dfs):
        return (
            Joiner.all_records(*dfs)
            .drop_duplicates("Município")
            .reset_index(drop=True)
        )
