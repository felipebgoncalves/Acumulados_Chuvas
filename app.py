import streamlit as st
import requests
import json
import pandas as pd
from PIL import Image
import plotly.express as px
import folium
from streamlit_folium import st_folium
from municipiosES import municipios_lat_lon_acumulados

img_1 = Image.open('img/logo_cepdec.png')
st.set_page_config(page_title="Acumulados de Chuva", page_icon=img_1, layout='wide', initial_sidebar_state="expanded")

img_2 = Image.open('img/cepdec.png')
st.image(img_2)

img_3 = Image.open('img/icon-chuva.png')


def acumulados():
    # CONSULTANDO OS DADOS ONLINE:

    url = 'http://salvar.cemaden.gov.br/resources/graficos/interativo/getJson2.php?uf=ES'

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


@st.cache_data
def convert_df(my_df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return my_df.to_csv().encode('utf-8')


# ==========================================================================================
# OBTENÇÃO DOS MÁXIMOS ATRAVÉS DA FUNÇÃO
maximos_1 = acumulados()

indices = range(1, len(maximos_1) + 1)
colunas = ['Município', '[mm]']

# DATAFRAME DA LISTA
df = pd.DataFrame(list(maximos_1.items()), index=indices, columns=colunas)

# ORGANIZAÇÃO DOS DADOS PARA PLOT
df_plot = df[0:20].sort_values(by='[mm]', ascending=True)

coordenadas_acumulado = municipios_lat_lon_acumulados(df)

# CONVERSÃO DOS DADOS PARA CSV
file_csv = convert_df(df)

# --------------------------------------------------------------------------------------------
# APLICAÇÃO DOS DADOS NO STREAMLIT
col1, col2 = st.columns([0.05, 0.95])

with col1:
    st.image(img_3)

with col2:
    st.title('ACUMULADOS DE CHUVA - CEMADEN')

st.text(
    """
    Script para verificação dos maiores acumulados de chuva de cada município do ES
     no período de 24h
    """
)
st.caption('Fonte dos dados: '
           'http://salvar.cemaden.gov.br/resources/graficos/interativo/grafico_CEMADEN.php?uf=ES#')

# CRIAÇÃO DE ABAS
tab1, tab2, tab3, tab4 = st.tabs(["MAPA 🗺️", "GRÁFICO 📊", "LISTA DE ACUMULADOS 📋", "TABELA DE ACUMULADOS 📌"])

# ABA 01
with tab1:
    st.markdown('**Acumulados de chuva em 24h:**')

    mapa = folium.Map(location=(-19.5382, -40.6324), zoom_start=8)

    for i, j in coordenadas_acumulado.items():

        if j[1] <= 10:
            html = f"""
                <h5><b>{i}<b></h5>
                <p>
                    {j[1]} mm
                 </p>
                """
            folium.Marker(
                location=j[0],
                tooltip=html,
                icon=folium.Icon(color='blue', icon='location-dot-solid.svg')
            ).add_to(mapa)

        elif 10 < j[1] <= 20:
            html = f"""
                    <h5><b>{i}<b></h5>
                    <p>
                        {j[1]} mm
                     </p>
                    """
            folium.Marker(
                location=j[0],
                tooltip=html,
                icon=folium.Icon(color='orange', icon='location-dot-solid.svg')
            ).add_to(mapa)

        elif j[1] > 20:
            html = f"""
                    <h5><b>{i}<b></h5>
                    <p>
                        {j[1]} mm
                     </p>
                    """
            folium.Marker(
                location=j[0],
                tooltip=html,
                icon=folium.Icon(color='red', icon='location-dot-solid.svg')
            ).add_to(mapa)

    st_data = st_folium(mapa, width=725)

# ABA 02
with tab2:
    if maximos_1 != '':

        fig = px.bar(df_plot, x='[mm]', y="Município", title="Acumulados de chuva em 24h", height=750)
        st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    elif maximos_1 == '':
        st.text('Sem acumulados de chuvas no momento!')

# ABA 03
with tab3:
    if maximos_1 != '':

        st.markdown('**Acumulados de chuva em 24h:**')
        for i, j in zip(maximos_1, range(1, len(maximos_1) + 1)):
            item = '{}. {} - {} mm'.format(j, i, maximos_1[i])
            st.text(item)

    elif maximos_1 == '':
        st.text('Sem acumulados de chuvas no momento!')

# ABA 04
with tab4:
    st.download_button(
        label="Download dos dados em CSV",
        data=file_csv,
        file_name='Acumulados24h.csv',
        mime='text/csv')

    st.dataframe(df)
