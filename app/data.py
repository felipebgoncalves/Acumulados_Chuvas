import json
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

from app.codEstacoes import INMET, ANA, CEPDEC, INCAPER

def acumulados_cemaden():
    # CONSULTANDO OS DADOS ONLINE:

    url = 'https://resources.cemaden.gov.br/graficos/interativo/getJson2.php?uf=ES'

    headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

    response = requests.get(url, headers=headers)

    text = json.loads(response.text)

    # REMOVENDO AS CIDADES QUE NÃO TEM MEDIÇÕES EM 24h:
    data = [x for x in text if x['acc24hr'] != '-']

    # REMOVENDO AS CIDADES COM MEDIÇÕES MENORES QUE 0:
    data = [x for x in data if x['acc24hr'] >= 0]

    # REMOVENDO OS DUPLICADOS MANTENDO O COM MAIOR VALOR NAS ÚLTIMAS 24H:
    maximos = {}

    for i in data:
        x, y = i['cidade'], i['acc24hr']
        if x not in maximos or y > maximos[x]:
            maximos[x] = y

    # ORDENANDO AS MEDIÇÕES EM ORDEM DECRESCENTE:
    maximos = dict(sorted(maximos.items(), key=lambda x: x[1], reverse=True))

    indices = range(1, len(maximos) + 1)
    colunas = ['Município', 'Prec_mm']

    # DATAFRAME DA LISTA
    df = pd.DataFrame(list(maximos.items()), index=indices, columns=colunas)
    df['Instituição'] = 'CEMADEN'

    # Arredonda a coluna de acumulados para 2 casas decimais para consistência na exibição
    df['Prec_mm'] = df['Prec_mm'].round(2)

    # ORGANIZAÇÃO DOS DADOS PARA PLOT
    df_cemaden = df[0:40].sort_values(by='Prec_mm', ascending=False)

    return df_cemaden


def acumulados_satdes():
    # Horário atual e 24h atrás
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)

    start_str = start_time.strftime("%Y-%m-%dT%H:%M")
    end_str = end_time.strftime("%Y-%m-%dT%H:%M")

    url = f"https://satdes-backend.incaper.es.gov.br/api/v1/records/monitoring/map/{start_str}/{end_str}"

    response = requests.get(url)
    data = response.json()

    prec_dict = data["data"]["prec"]

    registros = []

    for station_id, lista_medicoes in prec_dict.items():
        for item in lista_medicoes:

            if item.get("id_variable") == 15:

                codigo = item.get("name")

                # # Substituir código pelo município e Determinar instituição
                if codigo in INMET:
                    instituicao = "INMET"
                    municipio = INMET[codigo]

                elif codigo in ANA:
                    instituicao = "ANA"
                    municipio = ANA[codigo]

                elif codigo in CEPDEC:
                    instituicao = "CEPDEC"
                    municipio = CEPDEC[codigo]

                elif codigo in INCAPER:
                    instituicao = "INCAPER"
                    municipio = INCAPER[codigo]

                else:
                    instituicao = "DESCONHECIDA"
                    municipio = codigo  # mantém o código

                registros.append({
                    "Município": municipio,
                    "Prec_mm": item.get("instant", 0),
                    "Instituição": instituicao
                })                

    # Criar DataFrame
    df = pd.DataFrame(registros)

    # Se dataframe vier vazio, devolver vazio
    if df.empty:
        return pd.DataFrame(columns=["Município", "Prec_mm", "Instituição"])

    # Agrupar corretamente por MUNICIPIO (e não station_name)
    df_satdes = (
        df.groupby("Município").
        agg({
            "Prec_mm": "sum", 
            "Instituição": lambda x: x.mode()[0] if len(x.mode()) > 0 else "DESCONHECIDA"})
            .reset_index()
            )

     # FILTRAR SOMENTE PREC > 0
    df_satdes = df_satdes[df_satdes["Prec_mm"] > 0]
    
    df_satdes['Prec_mm'] = df_satdes['Prec_mm'].round(2)
    
    # ORDENAR em ordem decrescente
    df_satdes = df_satdes.sort_values(by="Prec_mm", ascending=False)
   
    return df_satdes


def join_acumulados(df1, df2):
    """
    df1 -> DataFrame do CEMADEN
    df2 -> DataFrame do SATDES
    """
    
    # Garantir que têm as colunas certas
    df1 = df1[["Município", "Prec_mm", "Instituição"]]
    df2 = df2[["Município", "Prec_mm", "Instituição"]]

    # Concatenar
    df = pd.concat([df1, df2], ignore_index=True)

    # Remover valores inválidos
    df = df[df["Prec_mm"] > 0]

    # AGRUPAR PEGANDO APENAS O MAIOR VALOR POR MUNICÍPIO
    df_plot = (
        df.loc[df.groupby("Município")["Prec_mm"].idxmax()]
        .sort_values(by="Prec_mm", ascending=False)
        .reset_index(drop=True))

    # Ordenar em ordem decrescente
    df_plot = df_plot.sort_values(by="Prec_mm", ascending=False).reset_index(drop=True)

    return df_plot



# PARA TESTE DO MÓDULO
# if __name__ == "__main__":
    # pd.set_option("display.max_rows", None)
    # print(join_acumulados(acumulados_cemaden(), acumulados_satdes()))
    