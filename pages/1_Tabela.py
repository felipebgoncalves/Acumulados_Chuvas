import streamlit as st

st.set_page_config(
    page_title="Tabela",
    page_icon="📋",
    layout="wide"
)

st.text('Tabela com os acumulados de chuva no período de 24h')


try:
    df = st.session_state.df

    st.dataframe(df)

except AttributeError as e:

    st.warning(e)
