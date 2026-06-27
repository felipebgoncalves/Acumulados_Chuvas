from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import folium
import pandas as pd
import streamlit as st
from folium import Element
from PIL import Image
from streamlit_folium import st_folium

from app.codEstacoes import ANA, INMET
from app.config.settings import (
    APP_TITLE,
    CACHE_TTL_SECONDS,
    EXTENDED_COLUMNS,
    SOURCE_ANA,
    SOURCE_CEMADEN,
    SOURCE_INMET,
    SOURCE_SATDES,
    get_env,
)
from app.dataCollector import AnaCollector, CemadenCollector, InmetCollector, Joiner, SatdesCollector
from app.municipiosES import municipios_lat_lon_acumulados
from app.render_header_footer import render_footer, render_header
from app.services.fonte_status import FonteStatus
from app.services.snapshots import salvar_snapshot_json

TZ_BRT = ZoneInfo("America/Sao_Paulo")


def get_secret(name: str, default: str | None = None) -> str | None:
    """Busca configuração primeiro no Streamlit secrets e depois no .env."""
    try:
        value = st.secrets.get(name)
        if value:
            return value
    except Exception:
        pass

    return get_env(name, default)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Buscando dados do CEMADEN...")
def load_cemaden():
    return CemadenCollector().get_dataframe()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Buscando dados do CEPDEC e INCAPER...")
def load_satdes():
    return SatdesCollector().get_dataframe()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Buscando dados da ANA...")
def load_ana(identificador: str, senha: str):
    collector = AnaCollector(
        identificador=identificador,
        senha=senha,
        estacoes_dict=ANA,
        max_workers=8,
    )
    return collector.fetch()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Buscando dados do INMET...")
def load_inmet(token: str):
    collector = InmetCollector(
        token=token,
        estacoes_dict=INMET,
        max_workers=8,
    )
    return collector.fetch()


def dataframe_vazio() -> pd.DataFrame:
    return pd.DataFrame(columns=EXTENDED_COLUMNS)


def coletar_fonte(nome: str, funcao, *args):
    try:
        df = funcao(*args)
        if df is None or df.empty:
            return dataframe_vazio(), FonteStatus.sucesso_coleta(nome, 0)

        return df, FonteStatus.sucesso_coleta(nome, len(df))
    except Exception as exc:
        return dataframe_vazio(), FonteStatus.falha_coleta(nome, exc)


def carregar_acumulados():
    dfs = []
    status = []

    df_cemaden, status_cemaden = coletar_fonte(SOURCE_CEMADEN, load_cemaden)
    dfs.append(df_cemaden)
    status.append(status_cemaden)

    df_satdes, status_satdes = coletar_fonte(SOURCE_SATDES, load_satdes)
    dfs.append(df_satdes)
    status.append(status_satdes)

    ana_id = get_secret("ANA_ID")
    ana_pwd = get_secret("ANA_PWD")
    if ana_id and ana_pwd:
        df_ana, status_ana = coletar_fonte(SOURCE_ANA, load_ana, ana_id, ana_pwd)
    else:
        df_ana, status_ana = dataframe_vazio(), FonteStatus.falha_coleta(
            SOURCE_ANA,
            "Credenciais ANA não configuradas.",
        )
    dfs.append(df_ana)
    status.append(status_ana)

    inmet_token = get_secret("INMET_API_TOKEN")
    if inmet_token:
        df_inmet, status_inmet = coletar_fonte(SOURCE_INMET, load_inmet, inmet_token)
    else:
        df_inmet, status_inmet = dataframe_vazio(), FonteStatus.falha_coleta(
            SOURCE_INMET,
            "Token INMET não configurado.",
        )
    dfs.append(df_inmet)
    status.append(status_inmet)

    try:
        df_final = Joiner.join(*dfs)
        salvar_snapshot_json(df_final)
        return df_final, status
    except Exception as exc:
        status.append(FonteStatus.falha_coleta("CONSOLIDAÇÃO", exc))
        return dataframe_vazio(), status


def cor_por_acumulado(valor: float) -> str:
    if valor <= 10:
        return "blue"
    if valor <= 20:
        return "orange"
    return "red"


def legenda_mapa() -> Element:
    html = """
    <div style="
        position: fixed;
        bottom: 45px;
        left: 45px;
        z-index: 9999;
        background-color: white;
        color: #000;
        padding: 10px 12px;
        border: 1px solid #bbb;
        border-radius: 6px;
        font-size: 13px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.25);
    ">
        <strong>Acumulado 24h</strong><br>
        <span style="color:#3388ff;">●</span> até 10 mm<br>
        <span style="color:#f59e0b;">●</span> 10 a 20 mm<br>
        <span style="color:#dc2626;">●</span> acima de 20 mm
    </div>
    """
    return Element(html)


def render_cards_resumo(df: pd.DataFrame, status: list[FonteStatus]) -> None:
    col1, col2, col3, col4, col5 = st.columns(5)

    if df.empty:
        maior = 0
        municipio = "-"
        municipios = 0
    else:
        maior_linha = df.sort_values("Prec_mm", ascending=False).iloc[0]
        maior = maior_linha["Prec_mm"]
        municipio = maior_linha["Município"]
        municipios = df["Município"].nunique()

    fontes_ativas = sum(1 for item in status if item.sucesso)
    agora = datetime.now(TZ_BRT).strftime("%d/%m/%Y %H:%M")

    col1.metric("Maior acumulado", f"{maior:.2f} mm")
    col2.metric("Município destaque", municipio)
    col3.metric("Municípios com chuva", municipios)
    col4.metric("Fontes ativas", fontes_ativas)
    col5.metric("Atualizado em", agora)


def render_mapa(df: pd.DataFrame) -> None:
    st.subheader("Mapa de Acumulados")
    mapa = folium.Map(location=(-19.6, -40.6), zoom_start=8)

    for municipio, dados in municipios_lat_lon_acumulados(df).items():
        coordenadas, acumulado = dados
        linha = df.loc[df["Município"] == municipio].iloc[0]

        estacao = linha.get("Estação") or "-"
        fonte = linha.get("Instituição") or linha.get("Fonte") or "-"
        referencia = linha.get("DataHoraReferencia") or "-"

        html = f"""
            <div style="font-size: 13px;">
                <strong>{municipio}</strong><br>
                Acumulado 24h: <strong>{acumulado:.2f} mm</strong><br>
                Fonte: {fonte}<br>
                Estação: {estacao}<br>
                Referência: {referencia}
            </div>
        """

        folium.Marker(
            location=coordenadas,
            tooltip=html,
            popup=html,
            icon=folium.Icon(color=cor_por_acumulado(acumulado), icon="cloud-rain", prefix="fa"),
        ).add_to(mapa)

    mapa.get_root().html.add_child(legenda_mapa())
    st_folium(mapa, width=1080, height=720)


def render_ranking(df: pd.DataFrame) -> None:
    st.subheader("Ranking de Acumulados")

    if df.empty:
        st.info("Sem dados para exibir.")
        return

    fontes = sorted(df["Instituição"].dropna().unique().tolist())
    filtro_fontes = st.multiselect("Filtrar por fonte", fontes, default=fontes)
    busca = st.text_input("Buscar município", "")

    tabela = df.copy()
    if filtro_fontes:
        tabela = tabela[tabela["Instituição"].isin(filtro_fontes)]

    if busca:
        tabela = tabela[tabela["Município"].str.contains(busca.upper(), na=False)]

    tabela = tabela.sort_values("Prec_mm", ascending=False).reset_index(drop=True)
    tabela.insert(0, "Posição", range(1, len(tabela) + 1))

    colunas = ["Posição", "Município", "Prec_mm", "Instituição"]
    altura_df = min((len(tabela) + 1) * 35 + 3, 700)

    st.dataframe(
        tabela[colunas],
        height=altura_df,
        hide_index=True,
        column_config={
            "Prec_mm": st.column_config.NumberColumn("Acumulado 24h (mm)", format="%.2f")
        },
    )


def render_lista(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Sem acumulados de chuvas no momento!")
        return

    df = df.reset_index(drop=True)
    st.markdown("**Acumulados de chuva em 24h:**")

    for index, row in df.iterrows():
        item = "{}. {} - {:.2f} mm".format(
            index + 1,
            row["Município"],
            row["Prec_mm"],
        )
        st.text(item)


def render_status_fontes(status: list[FonteStatus]) -> None:
    st.subheader("Status das fontes")
    if not status:
        st.info("Nenhuma fonte consultada.")
        return

    st.dataframe(
        pd.DataFrame([item.to_dict() for item in status]),
        hide_index=True,
        use_container_width=True,
    )


def run():
    img_1 = Image.open("img/logo_cepdec.png")
    st.set_page_config(page_title=APP_TITLE, page_icon=img_1, layout="wide")

    render_header()

    df, status = carregar_acumulados()
    render_cards_resumo(df, status)

    tab1, tab2, tab3 = st.tabs(["PRINCIPAL 📌", "LISTA DE ACUMULADOS 📋", "FONTES 🛰️"])

    with tab1:
        col1, col2 = st.columns([2, 1])
        with col1:
            render_mapa(df)
        with col2:
            render_ranking(df)

    with tab2:
        render_lista(df)

    with tab3:
        render_status_fontes(status)

    render_footer()
