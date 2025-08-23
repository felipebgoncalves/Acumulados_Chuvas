# app/data.py
import json
import requests
import pandas as pd

# ==== CÓDIGO DO app.py ====
def acumulados():
    # CONSULTANDO OS DADOS ONLINE:

    url = 'https://resources.cemaden.gov.br/graficos/interativo/getJson2.php?uf=ES'

    headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

    response = requests.get(url, headers=headers)

    text = json.loads(response.text)

    # REMOVENDO AS CIDADES QUE NÃO TEM MEDIÇÕES EM 24h:
    data = [x for x in text if x['acc24hr'] != '-']

    # REMOVENDO AS CIDADES COM MEDIÇÕES MENORES QUE 10:
    data = [x for x in data if x['acc24hr'] >= 0.]

    # REMOVENDO OS DUPLICADOS MANTENDO O COM MAIOR VALOR NAS ÚLTIMAS 24H:
    maximos = {}

    for i in data:
        x, y = i['cidade'], i['acc24hr']
        if x not in maximos or y > maximos[x]:
            maximos[x] = y

    # ORDENANDO AS MEDIÇÕES EM ORDEM DECRESCENTE:
    maximos = dict(sorted(maximos.items(), key=lambda x: x[1], reverse=True))

    indices = range(1, len(maximos) + 1)
    colunas = ['Município', '[mm]']

    # DATAFRAME DA LISTA
    df = pd.DataFrame(list(maximos.items()), index=indices, columns=colunas)

    # Arredonda a coluna de acumulados para 2 casas decimais para consistência na exibição
    # df['[mm]'] = df['[mm]'].round(2)

    # ORGANIZAÇÃO DOS DADOS PARA PLOT
    df_plot = df[0:40].sort_values(by='[mm]', ascending=False)

    return df_plot


# PARA TESTE DO MÓDULO
# if __name__ == "__main__":
#     print(acumulados())