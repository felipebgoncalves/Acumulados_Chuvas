import streamlit as st
from PIL import Image
from datetime import datetime

from app.weather import get_current_weather
from app.municipiosES import get_municipio_coords, COORDENADAS_ESPIRITO_SANTO


def render_header():

    img_2 = Image.open('img/cepdec.png')
    
    # Cria três colunas: a do meio será mais larga que as laterais
    col1, col2, col3 = st.columns([1, 6, 1])

    with col2:
        st.image(img_2)

    st.markdown("<h1 style='margin-bottom:0.2rem'>🌧️ Acumulados de Chuva</h1>", unsafe_allow_html=True)
    
    st.text("Script para verificação dos maiores acumulados de chuva de cada município do ES no período de 24h")
    
    st.caption('Fonte dos dados: http://www2.cemaden.gov.br/mapainterativo/# & https://satdes.incaper.es.gov.br')
        
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
    st.subheader(f"Condições Atuais em {municipio}/ES")
    
    # Coordenadas de exemplo para Colatina
    weather_data = get_current_weather(str(latitude), str(longitude))
    
    if not weather_data:
        st.warning("Não foi possível obter os dados do tempo no momento.")
        return
    
    # --- Hora atual no formato da API ---
    agora = datetime.now()  
    agora_str = agora.strftime("%Y-%m-%d %H:00")

    lista_horas = weather_data["data_1h"]["time"]

    try:
        idx = lista_horas.index(agora_str)
    except ValueError:
        st.error("Os dados do tempo para a hora atual não estão disponíveis.")
        return
    
    # --- Acessar os dados 1h ---
    data_1h = weather_data["data_1h"]

    # --- Extrair valores usando o mesmo índice ---
    resultado = {
        "hora": agora_str,
        "temperatura_C": data_1h["temperature"][idx],
        "umidade_%": data_1h["relativehumidity"][idx],
        "precipitacao_mm": data_1h["precipitation"][idx],
        "prob_chuva_%": data_1h["precipitation_probability"][idx],
        "vento_mps": data_1h["windspeed"][idx],

    }

    st.success("Dados meteorológicos atualizados:")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("🌡️ Temperatura", f"{resultado['temperatura_C']}°C")

    with col2:
        st.metric("💧 Umidade", f"{resultado['umidade_%']}%")

    with col3:
        st.metric("💨 Vento", f"{resultado['vento_mps']} m/s")

    with col4:
        st.metric("🌧️ Prob. Chuva", f"{resultado['prob_chuva_%']}%")

    st.markdown("---")
    st.caption("Deploy do aplicativo com Streamlit.")