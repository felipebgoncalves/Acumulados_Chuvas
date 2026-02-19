import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from dateutil.parser import parse
import certifi
import urllib3

from app.codEstacoes import INMET, ANA, CEPDEC, INCAPER

urllib3.disable_warnings()

# ==============================
# Mapa unificado de estações
# ==============================

MAPA_ESTACOES = {
    **{k: ("INMET", v) for k, v in INMET.items()},
    **{k: ("CEPDEC", v) for k, v in CEPDEC.items()},
    **{k: ("INCAPER", v) for k, v in INCAPER.items()},
}


class DataCollector:
    """Classe base para todos os coletores de acumulados."""
    def fetch(self):
        raise NotImplementedError("Implementar fetch() na classe filha.")

    def process(self):
        raise NotImplementedError("Implementar process() na classe filha.")

    def get_dataframe(self):
        """Método padrão usado pelo projeto."""
        data = self.fetch()
        return self.process(data)


class CemadenCollector(DataCollector):

    BASE_URL = "https://resources.cemaden.gov.br/graficos/interativo/getJson2.php?uf=ES"

    def fetch(self):
        headers = {'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'}
        response = requests.get(self.BASE_URL, headers=headers, timeout=30, verify=False)
        response.raise_for_status()

        return response.json()

    def process(self, data):
        
        df = pd.DataFrame(data)

        df = (
            df[df["acc24hr"] != "-"]
            .assign(acc24hr=lambda x: x["acc24hr"].astype(float))
            .query("acc24hr >= 0")
            .groupby("cidade", as_index=False)["acc24hr"]
            .max()
            .rename(columns={"cidade": "Município", "acc24hr": "Prec_mm"})
        )

        df["Instituição"] = "CEMADEN"
        df["Prec_mm"] = df["Prec_mm"].round(2)

        return df


class SatdesCollector(DataCollector):

    BASE_URL = "https://satdes-backend.incaper.es.gov.br/api/v1/records/monitoring/map"

    def fetch(self):
        end_utc = datetime.now(timezone.utc)
        start_utc = end_utc - timedelta(hours=24)

        url = f"{self.BASE_URL}/{start_utc.strftime("%Y-%m-%dT%H:%M")}/{end_utc.strftime("%Y-%m-%dT%H:%M")}"

        response = requests.get(url, timeout=30)
        
        return response.json(), start_utc, end_utc

    def process(self, payload):
        
        data, start_utc, end_utc = payload
        
        registros = []

        for lista in data["data"]["prec"].values():
            for item in lista:

                if "ANA" in item.get("code", ""):
                    continue

                date_utc = item.get("date_utc")
                if not date_utc:
                    continue

                ts_utc = datetime.fromisoformat(
                    date_utc.replace("Z", "+00:00")
                )

                if not (start_utc <= ts_utc <= end_utc):
                    continue

                name = item.get("name")
                inst, muni = MAPA_ESTACOES.get(name, ("DESCONHECIDA", name))

                registros.append({
                    "id_estacao": item.get("id_station"),
                    "Município": muni,
                    "Instituição": inst,
                    "Prec_mm": float(item.get("instant", 0))
                })

        df = pd.DataFrame(registros)

        if df.empty:
            return pd.DataFrame(columns=["Município", "Prec_mm", "Instituição"])

        df = (
            df.groupby(
                ["id_estacao", "Município", "Instituição"],
                as_index=False
            )["Prec_mm"]
            .sum()
        )

        df = df[df["Prec_mm"] > 0]
        df["Prec_mm"] = df["Prec_mm"].round(2)

        return df[["Município", "Prec_mm", "Instituição"]]


@st.cache_resource(ttl=900)  # 15 minutos
def obter_token_ana(identificador: str, senha: str) -> str:
    """
    Obtém e mantém em cache o token da ANA por 15 minutos.
    """
    url = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/OAUth/v1"

    headers = {
        "Identificador": identificador,
        "Senha": senha,
    }

    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()

    token = r.json().get("items", {}).get("tokenautenticacao")

    if not token:
        raise RuntimeError("Token ANA não retornado pela API.")

    return token


class AnaCollector(DataCollector):
    
    BASE_URL = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

    def __init__(self, identificador, senha, estacoes_dict, max_workers=8):
        self.identificador = identificador
        self.senha = senha
        self.estacoes = estacoes_dict
        self.max_workers = max_workers

    # ===================
    # CONSULTA INDIVIDUAL
    # ===================
    def _consulta_estacao(self, codigo, token):
        
        data_busca = datetime.now().strftime("%Y-%m-%d")

        url = (
            f"{self.BASE_URL}/HidroinfoanaSerieTelemetricaAdotada/v1"
            f'?Código da Estação={codigo}'
            f'&Tipo Filtro Data=DATA_LEITURA'
            f'&Data de Busca (yyyy-MM-dd)={data_busca}'
            f'&Range Intervalo de busca=DIAS_2'
            )

        headers = {
            "Authorization": f"Bearer {token}"
            }

        r = requests.get(url, headers=headers, timeout=30)
        return codigo, r.json()
    
    # =====================================
    # SOMA DOS ÚLTIMOS 24h - FETCH (PARALELIZADO)
    # =====================================
    def fetch(self):
        
        tz_brt = ZoneInfo("America/Sao_Paulo")

        end_utc = datetime.now(timezone.utc)
        start_utc = end_utc - timedelta(hours=24)

        registros = []

        # Token obtido apenas uma vez
        token = obter_token_ana(self.identificador, self.senha)

        # Chamadas paralelas
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:

            futures = {
                executor.submit(self._consulta_estacao, cod, token): (cod, muni)
                for cod, muni in self.estacoes.items()
            }

            for future in as_completed(futures):

                cod, muni = futures[future]

                try:
                    _, payload = future.result()
                    items = payload.get("items", [])

                    soma = 0.0

                    for item in items:
                        data_str = item.get("Data_Hora_Medicao")
                        if not data_str:
                            continue

                        try:
                            ts = parse(data_str)
                            ts = ts.replace(tzinfo=tz_brt).astimezone(timezone.utc)
                        except Exception:
                            continue

                        if not (start_utc <= ts <= end_utc):
                            continue

                        soma += float(item.get("Chuva_Adotada") or 0)

                    if soma > 0:
                        registros.append({
                            "Estacao": cod,
                            "Município": muni,
                            "Instituição": "ANA",
                            "Prec_mm": round(soma, 2)
                        })

                except Exception as e:
                    print(f"Erro na estação {cod}: {e}")

        # DataFrame final
        if not registros:
            return pd.DataFrame(columns=["Município", "Prec_mm", "Instituição"])

        df = (
            pd.DataFrame(registros)
              .sort_values(by="Prec_mm", ascending=False)
              .reset_index(drop=True)
        )

        return df[["Município", "Prec_mm", "Instituição"]]


class Joiner:

    @staticmethod
    def join(*dfs):
        
        # Concatena todos os DataFrames recebidos
        df = pd.concat(
            [
                df_[["Município", "Prec_mm", "Instituição"]]
                for df_ in dfs
            ],
            ignore_index=True
        )
        
        # Filtra apenas valores positivos
        df = df[df["Prec_mm"] > 0]

        df_plot = (
            df.sort_values("Prec_mm", ascending=False)
              .drop_duplicates("Município")
              .reset_index(drop=True)
        )

        return df_plot