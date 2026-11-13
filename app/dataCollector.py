from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from math import isfinite
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

from app.codEstacoes import ANA, CEPDEC, INMET
from app.config.settings import (
    ANA_BASE_URL,
    ANA_TOKEN_TTL_SECONDS,
    ANA_TOKEN_URL,
    CEMADEN_URL,
    EXTENDED_COLUMNS,
    INMET_BASE_URL,
    PMVV_BASE_URL,
    REQUEST_TIMEOUT_SECONDS,
    SOURCE_ANA,
    SOURCE_CEMADEN,
    SOURCE_CEPDEC,
    SOURCE_INMET,
    SOURCE_PMVV,
)
from app.services.estacoes import carregar_base_estacoes
from app.services.normalizacao import (
    garantir_colunas_estendidas,
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


class CepdecCollector(DataCollector):
    """Chuva por estação da CEPDEC, preservando e sinalizando séries parciais."""

    fonte = SOURCE_CEPDEC
    MAX_PAGES = 10

    def __init__(
        self, base_url: str, token_url: str, client_id: str, client_secret: str,
        api_key: str, grant_type: str = "client_credentials",
        estacoes_dict: dict | None = None, max_workers: int = 4,
    ):
        self.base_url = base_url.rstrip("/")
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_key = api_key
        self.grant_type = grant_type
        self.estacoes = dict(CEPDEC if estacoes_dict is None else estacoes_dict)
        self.max_workers = max(1, min(max_workers, 4))

    @staticmethod
    def _timestamp(item: dict) -> datetime | None:
        try:
            ts = datetime.fromisoformat(item["data_hora_utc"].replace("Z", "+00:00"))
            return ts.astimezone(timezone.utc) if ts.tzinfo else None
        except (KeyError, TypeError, ValueError, AttributeError):
            return None

    def _token(self) -> str:
        try:
            response = requests.post(
                self.token_url,
                data={"grant_type": self.grant_type, "client_id": self.client_id,
                      "client_secret": self.client_secret},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            token = response.json().get("access_token")
            if not isinstance(token, str) or not token:
                raise ValueError("token ausente")
            return token
        except Exception as exc:
            raise RuntimeError(f"Autenticação CEPDEC: {erro_http_resumido(exc)}") from None

    def _consultar_estacao(self, codigo: str, headers: dict, inicio: datetime):
        params = {"estacao": codigo, "intervalo_minutos": 15}
        leituras, cursores = [], set()
        for _ in range(self.MAX_PAGES):
            try:
                response = requests.get(
                    f"{self.base_url}/v1/observacoes", params=params,
                    headers=headers, timeout=REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get("items"), list):
                    return leituras, "resposta de observações inválida"
                items = data["items"]
                if any(not isinstance(item, dict) for item in items):
                    return leituras, "resposta de observações inválida"
                leituras.extend(items)
                timestamps = [self._timestamp(item) for item in items]
                # A API pagina do mais recente para o mais antigo.
                if timestamps and all(ts is not None for ts in timestamps):
                    if timestamps == sorted(timestamps, reverse=True) and timestamps[-1] <= inicio:
                        return leituras, ""
                cursor = data.get("next_cursor")
                if not cursor:
                    return leituras, ""
                if not isinstance(cursor, str) or cursor in cursores or not items:
                    return leituras, "paginação interrompida: cursor inválido ou repetido"
                cursores.add(cursor)
                params = {**params, "cursor": cursor}
            except Exception as exc:
                return leituras, erro_http_resumido(exc)
        return leituras, "paginação interrompida: limite de páginas atingido"

    def fetch(self, now: datetime | None = None) -> pd.DataFrame:
        fim = now or datetime.now(timezone.utc)
        if fim.tzinfo is None:
            raise ValueError("A referência CEPDEC deve incluir fuso horário.")
        fim = fim.astimezone(timezone.utc)
        inicio = fim - timedelta(hours=24)
        headers = {"Authorization": f"Bearer {self._token()}", "x-api-key": self.api_key}
        payload = {"inicio": inicio, "fim": fim, "leituras": {}, "metadados": {},
                   "erros": {}, "avisos": []}
        try:
            response = requests.get(
                f"{self.base_url}/v1/estacoes", headers=headers, timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            items = response.json()
            if not isinstance(items, list):
                raise ValueError("metadados inválidos")
            payload["metadados"] = {item["codigo"]: item for item in items}
        except Exception as exc:
            payload["avisos"].append(f"Metadados CEPDEC indisponíveis: {erro_http_resumido(exc)}")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._consultar_estacao, codigo, headers, inicio): codigo
                       for codigo in self.estacoes}
            for future in as_completed(futures):
                codigo = futures[future]
                leituras, erro = future.result()
                payload["leituras"][codigo] = leituras
                if erro:
                    payload["erros"][codigo] = erro

        df = self.process(payload)
        if df.empty and payload["erros"]:
            raise RuntimeError("CEPDEC sem leituras válidas. " + "; ".join(df.attrs["avisos"]))
        return df

    def get_dataframe(self):
        return self.fetch()

    def process(self, payload) -> pd.DataFrame:
        inicio, fim = payload["inicio"], payload["fim"]
        registros, avisos = [], list(payload.get("avisos", []))
        for codigo, municipio in self.estacoes.items():
            validas, descartadas = {}, 0
            for item in payload["leituras"].get(codigo, []):
                if item.get("estacao_codigo") != codigo:
                    continue
                ts = self._timestamp(item)
                if ts is None:
                    descartadas += 1
                    continue
                if not inicio < ts <= fim:
                    continue
                dados = item.get("dados")
                valor = dados.get("PRECIPITACAO_MM") if isinstance(dados, dict) else None
                chuva = to_float(valor, default=float("nan"))
                if (isinstance(valor, bool) or not isfinite(chuva) or chuva < 0
                        or item.get("intervalo_minutos") != 15
                        or item.get("qualidade") != "VALIDO" or item.get("flags")):
                    descartadas += 1
                    continue
                if ts in validas and validas[ts] != chuva:
                    descartadas += 1
                validas.setdefault(ts, chuva)

            observacoes = []
            horarios = sorted(validas)
            # Uma janela de 24h contém 96 intervalos de 15 minutos.
            # Tolerância de 1 minuto para pequenas variações no relógio da estação.
            limites = [inicio, *horarios, fim]
            lacuna = any(b - a > timedelta(minutes=16) for a, b in zip(limites, limites[1:]))
            if len(validas) < 96 or lacuna:
                observacoes.append(f"Acumulado parcial: {len(validas)}/96 leituras válidas nas últimas 24h")
            if descartadas:
                observacoes.append(f"{descartadas} leitura(s) inválida(s) ou conflitante(s) descartada(s)")
            erro = payload.get("erros", {}).get(codigo)
            if erro:
                observacoes.append(f"Consulta incompleta: {erro}")
            if not validas:
                observacoes.append("Sem chuva mensurável disponível; não equivale a zero de chuva")
            observacao = "; ".join(observacoes)
            if observacao:
                avisos.append(f"{codigo} ({municipio}): {observacao}")
            if not validas:
                continue
            meta = payload.get("metadados", {}).get(codigo, {})
            registros.append({
                "Município": municipio, "Prec_mm": round(sum(validas.values()), 2),
                "Instituição": SOURCE_CEPDEC, "Estação": codigo,
                "Latitude": meta.get("latitude"), "Longitude": meta.get("longitude"),
                "Altitude": meta.get("altitude_m"),
                "DataHoraReferencia": max(validas).astimezone(TZ_BRT).isoformat(),
                "Fonte": SOURCE_CEPDEC, "Observação": observacao,
            })
        df = self.finalize(pd.DataFrame(registros))
        df.attrs["avisos"] = avisos
        return df


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
