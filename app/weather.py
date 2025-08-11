import os
import requests
import streamlit as st

@st.cache_data(ttl=600) # Cache por 10 minutos (600 segundos)
def get_current_weather(latitude: str, longitude: str) -> dict | None:
    
    try:
        API_KEY = st.secrets["API_KEY"]

    except KeyError:
        st.error("A variável 'API_KEY' não foi encontrada nos segredos.")
        st.info("Por favor, configure a chave de API nos segredos do seu app no Streamlit Cloud.")

    url = f"https://weather.googleapis.com/v1/currentConditions:lookup?key={API_KEY}&location.latitude={latitude}&location.longitude={longitude}&languageCode=pt"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        st.warning(f"Não foi possível buscar os dados do tempo: {e}")
        return None