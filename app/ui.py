import streamlit as st
from PIL import Image

from app.weather import get_current_weather
from app.municipiosES import get_municipio_coords, COORDENADAS_ESPIRITO_SANTO


def render_header():

    img_2 = Image.open('img/cepdec.png')
    
    # Cria três colunas: a do meio será mais larga que as laterais
    col1, col2, col3 = st.columns([1, 6, 1])

    # A coluna 1 (col1) e 3 (col3) ficam vazias, atuando como espaçamento
    # Colocamos a imagem na coluna do meio (col2)
    with col2:
        st.image(img_2)

    st.markdown("<h1 style='margin-bottom:0.2rem'>🌧️ Acumulados de Chuva</h1>", unsafe_allow_html=True)
    
    st.text("Script para verificação dos maiores acumulados de chuva de cada município do ES no período de 24h")
    
    st.caption('Fonte dos dados: http://www2.cemaden.gov.br/mapainterativo/#')
    
    st.markdown("---")


def render_footer():
    st.markdown("---")

    lista_municipios = list(COORDENADAS_ESPIRITO_SANTO.keys())
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        municipio = st.selectbox(label="Municípios do ES", options=lista_municipios, index=77)
    
    dados_municipio = get_municipio_coords(municipio=municipio)
    coordenadas = list(dados_municipio.values())[0]
    latitude, longitude = coordenadas
    
    # --- Previsão do tempo atual ---
    st.subheader(f"Condições Atuais em {next(iter(dados_municipio))}/ES")
    
    # Coordenadas de exemplo para Colatina
    # weather_data = get_current_weather("-19.5382", "-40.6324")
    weather_data = get_current_weather(str(latitude), str(longitude))
    
    if weather_data:
        temp = weather_data.get('temperature', {})
        humidity = weather_data.get('relativeHumidity')
        presipitation = weather_data.get('precipitation', {}).get('probability', {}).get('percent', {})

        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        col1.metric(label="Temperatura 🌡️", value=f"{temp.get('degrees', '--')} °C")
        col2.metric(label="Umidade 💧", value=f"{humidity}%" if humidity is not None else "-- %")
        col3.metric(label="Precipitação 🌦️", value=f"{presipitation}%" if presipitation is not None else "-- %")
    else:
        st.warning("Dados do tempo indisponíveis.")


    st.markdown("---")
    st.caption("Deploy do aplicativo com Streamlit.")

    


