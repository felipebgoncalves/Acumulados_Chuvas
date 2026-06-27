import streamlit as st
from PIL import Image

from app.config.settings import APP_SUBTITLE, APP_TITLE


def render_header():

    img_2 = Image.open('img/cepdec.png')
    
    # Cria três colunas: a do meio será mais larga que as laterais
    col1, col2, col3 = st.columns([1, 6, 1])

    with col2:
        st.image(img_2)

    st.markdown(f"<h1 style='margin-bottom:0.2rem'>🌧️ {APP_TITLE}</h1>", unsafe_allow_html=True)
    
    st.text(APP_SUBTITLE)
    
    st.caption('Fonte dos dados:')
    st.caption('CEMADEN [http://www2.cemaden.gov.br/mapainterativo/#]')
    st.caption('ANA [https://www.snirh.gov.br/hidrotelemetria/Mapa.aspx]')
    st.caption('INMET [https://portal.inmet.gov.br/]')
    st.caption('SATDES — CEPDEC e INCAPER [https://satdes.incaper.es.gov.br]')

    st.markdown("---")


def render_footer():
    
    st.markdown("---")
    st.caption("Aplicativo operacional publicado com Streamlit.")
