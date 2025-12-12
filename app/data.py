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
    # em UTC
    agora_utc = datetime.now(timezone.utc)
    inicio_utc = agora_utc - timedelta(hours=24)

    # Gerar strings no formato da API (também em UTC)
    start_str = inicio_utc.strftime("%Y-%m-%dT%H:%M")
    end_str = agora_utc.strftime("%Y-%m-%dT%H:%M")

    url = f"https://satdes-backend.incaper.es.gov.br/api/v1/records/monitoring/map/{start_str}/{end_str}"
    
    response = requests.get(url)
    data = response.json()

    prec_dict = data["data"]["prec"]

    registros = []

    for _, lista in prec_dict.items():
        for item in lista:

            # ➤ EXCLUIR estações ANA
            if "ANA" in item.get("code", ""):
                continue

            # pegar timestamp UTC vindo da API
            date_utc_str = item.get("date_utc")
            if not date_utc_str:
                continue

            ts_utc = datetime.fromisoformat(date_utc_str.replace("Z", "+00:00"))

            # filtrar somente dentro do intervalo UTC pedido
            if not (inicio_utc <= ts_utc <= agora_utc):
                continue

            # identificar um id único de estação 
            id_estacao = item.get("id_station")

            # pegar código/nome da estação (campo "name" contém ex: EMA_COL_01)
            name = item.get("name")

            # identificar instituicao/municipio pelos dicionários (INMET, ANA, CEPDEC, INCAPER)
            if name in INMET:
                instituicao = "INMET"
                municipio = INMET[name]

            # elif name in ANA:
            #     instituicao = "ANA"
            #     municipio = ANA[name]

            elif name in CEPDEC:
                instituicao = "CEPDEC"
                municipio = CEPDEC[name]

            elif name in INCAPER:
                instituicao = "INCAPER"
                municipio = INCAPER[name]

            else:
                instituicao = "DESCONHECIDA"
                municipio = name

            registros.append({
                "id_estacao": id_estacao,
                "Estacao": name,
                "Município": municipio,
                "Instituição": instituicao,
                "Prec_mm": float(item.get("instant", 0))
            })               

    # Criar DataFrame
    df = pd.DataFrame(registros)

    # Se vazio, retorna estrutura vazia consistente
    if df.empty:
        return pd.DataFrame(columns=["id_estacao", "Estacao", "Município", "Prec_mm", "Instituição"])

    # SOMA APENAS POR ESTAÇÃO (chaves: id_estacao, Estacao, Instituição, Município)
    # Isto garante que estações diferentes (mesmo município e/ou mesma instituição) não terão suas chuvas misturadas.
    df_satdes = (
        df.groupby(["id_estacao", "Estacao", "Município", "Instituição"], dropna=False)["Prec_mm"]
          .sum()
          .reset_index()
    )

    # filtrar apenas > 0 (estações com chuva)
    df_satdes = df_satdes[df_satdes["Prec_mm"] > 0]

    # arredondar e ordenar
    df_satdes["Prec_mm"] = df_satdes["Prec_mm"].round(2)
    df_satdes = df_satdes.sort_values(by="Prec_mm", ascending=False).reset_index(drop=True)

    df_satdes = df_satdes[["Município", "Prec_mm", "Instituição"]]
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

# --------------------
# PARA TESTE DO MÓDULO
# if __name__ == "__main__":
    
#     pd.set_option("display.max_rows", None)
#     print(join_acumulados(acumulados_cemaden(), acumulados_satdes()))