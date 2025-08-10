import streamlit as st
import pandas as pd
from streamlit_folium import st_folium
import folium
from PIL import Image

from app.municipiosES import municipios_lat_lon_acumulados as coordenadas_acumulado
from app.ui import render_header, render_footer
from app import data

def run():
    img_1 = Image.open('img/logo_cepdec.png')
    st.set_page_config(page_title="Acumulados de Chuva", page_icon=img_1, layout="wide")
    
    render_header()

    # DataFrame dos municipios que possuem acumulados no momento
    df = data.acumulados()

    # CRIAÇÃO DE ABAS
    tab1, tab2 = st.tabs(["PRINCIPAL 📌", "LISTA DE ACUMULADOS 📋"])

    # ABA 1
    with tab1:

        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("Mapa de Acumulados")
            
            mapa = folium.Map(location=(-19.5382, -40.6324), zoom_start=8)

            for i, j in coordenadas_acumulado(df).items():

                if j[1] <= 10:
                    html = f"""
                        <h6><b>{i}<b></h6>
                        <p>
                            prec: {j[1]} mm
                        </p>
                        """
                    folium.Marker(
                        location=j[0],
                        tooltip=html,
                        icon=folium.Icon(color='blue', icon='location-dot-solid.svg')
                    ).add_to(mapa)

                elif 10 < j[1] <= 20:
                    html = f"""
                            <h6><b>{i}<b></h6>
                            <p>
                                prec: {j[1]} mm
                            </p>
                            """
                    folium.Marker(
                        location=j[0],
                        tooltip=html,
                        icon=folium.Icon(color='orange', icon='location-dot-solid.svg')
                    ).add_to(mapa)

                elif j[1] > 20:
                    html = f"""
                            <h6><b>{i}<b></h6>
                            <p>
                                prec: {j[1]} mm
                            </p>
                            """
                    folium.Marker(
                        location=j[0],
                        tooltip=html,
                        icon=folium.Icon(color='red', icon='location-dot-solid.svg')
                    ).add_to(mapa)

            st_folium(mapa, width=725)


        with col2:

            # TABELA
            st.subheader("Ranking de Acumulados")

            if not df.empty:
                # Para controlar o formato, usamos st.dataframe().
                # 1. `column_config` formata a coluna '[mm]' para ter exatamente 2 casas decimais.
                # 2. `height` é calculado para exibir todas as linhas sem barra de rolagem.
                # 3. `hide_index=True` remove a coluna de índice para um visual mais limpo.
                altura_df = (len(df) + 1) * 35 + 3
                st.dataframe(
                    df,
                    height=altura_df,
                    hide_index=True,
                    column_config={
                        "[mm]": st.column_config.NumberColumn(format="%.2f")
                    },
                )
            else:
                st.info("Sem dados para exibir.")

        render_footer()

    # ABA 2
    with tab2:
        
        if not df.empty:

            df = df.reset_index(drop=True)

            st.markdown('**Acumulados de chuva em 24h:**')
            
            for index, row in df.iterrows():
                # Criamos o contador 'j' somando 1 ao índice
                j = index + 1
                # Acessamos os valores da linha pelos nomes das colunas
                municipio = row['Município']
                acumulado = row['[mm]']

                # Formatamos a string como antes
                item = '{}. {} - {} mm'.format(j, municipio, acumulado)
                st.text(item)

        else:
            st.text('Sem acumulados de chuvas no momento!')
