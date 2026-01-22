from tkinter import Image
import requests
import streamlit as st
from PIL import Image

@st.cache_data(ttl=600) # Cache por 10 minutos (600 segundos)
def get_current_weather(latitude: str, longitude: str) -> dict | None:
    
    API_KEY = st.secrets["API_KEY"]

    if not API_KEY:
        st.error("API_KEY não encontrada nos segredos.")
        return None

    url = f"https://my.meteoblue.com/packages/basic-1h?lat={latitude}&lon={longitude}&apikey={API_KEY}&forecast_days=1&tz=America%2FSao_Paulo"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        st.warning(f"Não foi possível buscar os dados do tempo: \n\n{e}")
        return None