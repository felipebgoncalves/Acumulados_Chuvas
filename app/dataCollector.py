import json
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.codEstacoes import INMET, ANA, CEPDEC, INCAPER

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

    URL = "https://resources.cemaden.gov.br/graficos/interativo/getJson2.php?uf=ES"

    def fetch(self):
        headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
        response = requests.get(self.URL, headers=headers)
        return json.loads(response.text)

    def process(self, text):
        # Remover sem dados
        data = [x for x in text if x['acc24hr'] != '-']

        # Remover negativos
        data = [x for x in data if x['acc24hr'] >= 0]

        # Remover duplicados por município -> maior valor
        maximos = {}
        for item in data:
            mun = item['cidade']
            val = item['acc24hr']
            if mun not in maximos or val > maximos[mun]:
                maximos[mun] = val

        # Ordenar
        maximos = dict(sorted(maximos.items(), key=lambda x: x[1], reverse=True))

        df = pd.DataFrame(
            list(maximos.items()),
            index=range(1, len(maximos)+1),
            columns=["Município", "Prec_mm"]
        )

        df["Instituição"] = "CEMADEN"
        df["Prec_mm"] = df["Prec_mm"].round(2)

        return df.sort_values(by="Prec_mm", ascending=False).reset_index(drop=True)
    

class SatdesCollector(DataCollector):

    BASE_URL = "https://satdes-backend.incaper.es.gov.br/api/v1/records/monitoring/map"

    def fetch(self):
        agora_utc = datetime.now(timezone.utc)
        inicio_utc = agora_utc - timedelta(hours=24)

        start_str = inicio_utc.strftime("%Y-%m-%dT%H:%M")
        end_str = agora_utc.strftime("%Y-%m-%dT%H:%M")

        url = f"{self.BASE_URL}/{start_str}/{end_str}"

        response = requests.get(url)
        return response.json(), inicio_utc, agora_utc

    def process(self, payload):
        data, inicio_utc, agora_utc = payload

        prec_dict = data["data"]["prec"]
        registros = []

        for _, lista in prec_dict.items():
            for item in lista:

                # excluir ANA
                if "ANA" in item.get("code", ""):
                    continue

                date_utc_str = item.get("date_utc")
                if not date_utc_str:
                    continue

                ts_utc = datetime.fromisoformat(date_utc_str.replace("Z", "+00:00"))

                if not (inicio_utc <= ts_utc <= agora_utc):
                    continue

                id_estacao = item.get("id_station")
                name = item.get("name")

                # descobrir instituição
                if name in INMET:
                    inst = "INMET"
                    muni = INMET[name]
                # elif name in ANA:
                #     inst = "ANA"
                #     muni = ANA[name]
                elif name in CEPDEC:
                    inst = "CEPDEC"
                    muni = CEPDEC[name]
                elif name in INCAPER:
                    inst = "INCAPER"
                    muni = INCAPER[name]
                else:
                    inst = "DESCONHECIDA"
                    muni = name

                registros.append({
                    "id_estacao": id_estacao,
                    "Estacao": name,
                    "Município": muni,
                    "Instituição": inst,
                    "Prec_mm": float(item.get("instant", 0))
                })

        df = pd.DataFrame(registros)

        if df.empty:
            return pd.DataFrame(columns=["Município", "Prec_mm", "Instituição"])

        df_satdes = (
            df.groupby(["id_estacao", "Estacao", "Município", "Instituição"])["Prec_mm"]
              .sum()
              .reset_index()
        )

        df_satdes = df_satdes[df_satdes["Prec_mm"] > 0]
        df_satdes["Prec_mm"] = df_satdes["Prec_mm"].round(2)

        df_satdes = df_satdes.sort_values(by="Prec_mm", ascending=False)
        df_satdes = df_satdes.reset_index(drop=True)

        return df_satdes[["Município", "Prec_mm", "Instituição"]]


class AnaCollector(DataCollector):
    BASE_URL = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

    def __init__(self, identificador, senha, estacoes_dict):
        self.identificador = identificador
        self.senha = senha
        self.estacoes = estacoes_dict
        self.token = None
        self.token_time = None

    # =========
    # TOKEN
    # ========
    def _token_valido(self):
        if self.token is None:
            return False
        return datetime.now() < self.token_time + timedelta(minutes=15)
    
    def _obter_token(self):
        url = f"{self.BASE_URL}/OAUth/v1"
        headers = {
            "Identificador": self.identificador,
            "Senha": self.senha
            }
        r = requests.get(url, headers=headers).json()
        self.token = r.get("items", {}).get("tokenautenticacao")
        self.token_time = datetime.now()

    def _get_token(self):
        if not self._token_valido():
            self._obter_token()
        return self.token
    
    # ===================
    # CONSULTA INDIVIDUAL
    # ===================
    def _consulta_estacao(self, codigo):
        token = self._get_token()
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

        r = requests.get(url, headers=headers)
        return r.json()
    
    # =====================================
    # SOMA DOS ÚLTIMOS 24h
    # =====================================
    def fetch(self):
        """Consulta todas as estações e retorna DataFrame final."""
        tz_brt = ZoneInfo("America/Sao_Paulo")

        agora_utc = datetime.now(timezone.utc)
        inicio_utc = agora_utc - timedelta(hours=24)

        registros = []

        for cod, muni in self.estacoes.items():

            try:
                payload = self._consulta_estacao(cod)
                items = payload.get("items", [])

                soma = 0.0

                for item in items:
                    data_str = item.get("Data_Hora_Medicao")
                    if not data_str:
                        continue

                    ts = datetime.fromisoformat(data_str.replace(" ", "T")).replace(tzinfo=tz_brt).astimezone(timezone.utc)

                    if inicio_utc <= ts <= agora_utc:
                        chuva = float(item.get("Chuva_Adotada", 0) or 0)
                        soma += chuva

                if soma > 0:
                    registros.append({
                        "Estacao": cod,
                        "Município": muni,
                        "Instituição": "ANA",
                        "Prec_mm": round(soma, 2)
                    })

            except Exception as e:
                print(f"Erro na estação {cod}: {e}")
                continue

        # DataFrame final
        if not registros:
            return pd.DataFrame(columns=["Município", "Prec_mm", "Instituição"])

        df = pd.DataFrame(registros)
        df_ana = df.sort_values(by="Prec_mm", ascending=False).reset_index(drop=True)

        # return df_ana[["Município", "Prec_mm", "Instituição", "Estacao"]]
        return df_ana[["Município", "Prec_mm", "Instituição"]]


class Joiner:

    @staticmethod
    def join(df1, df2, df3):

        df1 = df1[["Município", "Prec_mm", "Instituição"]]
        df2 = df2[["Município", "Prec_mm", "Instituição"]]
        df3 = df3[["Município", "Prec_mm", "Instituição"]]

        df = pd.concat([df1, df2, df3], ignore_index=True)
        
        df = df[df["Prec_mm"] > 0]

        df_plot = (
            df.loc[df.groupby("Município")["Prec_mm"].idxmax()]
            .sort_values(by="Prec_mm", ascending=False)
            .reset_index(drop=True)
        )

        return df_plot


# =====================
# TESTE DO MÓDULO
# =====================
# from dotenv import load_dotenv

# if __name__ == "__main__":
    
#     pd.set_option("display.max_rows", None)

#     load_dotenv()

#     identificador = os.getenv("ANA_ID")
#     senha = os.getenv("ANA_PWD")

#     cemaden = CemadenCollector()
#     satdes = SatdesCollector()
#     ana = AnaCollector(
#         identificador=identificador,
#         senha=senha,
#         estacoes_dict=ANA
#     )

#     df_cemaden = cemaden.get_dataframe()
#     df_satdes  = satdes.get_dataframe()
#     df_ana = ana.fetch()

#     df_final = Joiner.join(df_cemaden, df_satdes, df_ana)

#     print(df_final)