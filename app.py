import streamlit as st
import requests
import json
import pandas as pd
from PIL import Image
import plotly.express as px


def acumulados():
    # CONSULTANDO OS DADOS ONLINE:

    url = 'http://sjc.salvar.cemaden.gov.br/resources/graficos/interativo/getJson2.php?uf=ES'

    headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

    response = requests.get(url, headers=headers)

    text = json.loads(response.text)

    # REMOVENDO AS CIDADES QUE NÃO TEM MEDIÇÕES EM 24h:
    data = [x for x in text if x['acc24hr'] != '-']

    # REMOVENDO AS CIDADES COM MEDIÇÕES MENORES QUE 10:
    data = [x for x in data if x['acc24hr'] >= 1]

    # REMOVENDO OS DUPLICADOS MANTENDO O COM MAIOR VALOR NAS ÚLTIMAS 24H:
    maximos = {}

    for i in data:
        x, y = i['cidade'], i['acc24hr']
        if x not in maximos or y > maximos[x]:
            maximos[x] = y

    # ORDENANDO AS MEDIÇÕES EM ORDEM DECRESCENTE:
    maximos = dict(sorted(maximos.items(), key=lambda x: x[1], reverse=True))

    return maximos


@st.cache
def convert_df(my_df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return my_df.to_csv().encode('utf-8')


maximos1 = acumulados()

indices = range(1, len(maximos1) + 1)
colunas = ['Município', '[mm]']
df = pd.DataFrame(list(maximos1.items()), index=indices, columns=colunas)

df_plot = df[0:20].sort_values(by='[mm]', ascending=True)

file_csv = convert_df(df)

imagem = Image.open('cepdec.png')
st.image(imagem)

st.title('ACUMULADOS DE CHUVA - CEMADEN')
st.text('Algoritmo para verificação dos acumulados de chuva no período de 24h')

itemSelecionado = st.selectbox('Selecione o que deseja visualizar:',
                               ['Gráfico', 'Lista de acumulados', 'Download da tabela de acumulados'],
                               )

if itemSelecionado == 'Gráfico':

    if maximos1 != '':

        fig = px.bar(df_plot, x='[mm]', y="Município", title="Acumulados de chuva em 24h")
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.text('Sem acumulados de chuvas no momento!')


elif itemSelecionado == 'Lista de acumulados':

    if maximos1 != '':

        for i, j in zip(maximos1, range(1, len(maximos1) + 1)):
            item = '{}. {} - {} mm'.format(j, i, maximos1[i])
            st.text(item)

    else:
        st.text('Sem acumulados de chuvas no momento!')


elif itemSelecionado == 'Download da tabela de acumulados':

    st.download_button(
        label="Download dos dados em CSV",
        data=file_csv,
        file_name='Acumulados.csv',
        mime='text/csv')
