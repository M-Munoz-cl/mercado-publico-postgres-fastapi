import streamlit as st


st.set_page_config(
    page_title="Herramientas Mercado Público",
    page_icon="📋",
    layout="wide"
)

# Definir páginas
buscador_page = st.Page(
    "app/pages/buscador.py",
    title="Buscador de Compras Ágiles",
    icon="🔎",
    default=True
)

fichas_page = st.Page(
    "app/pages/generador_fichas.py",
    title="Generador de fichas técnicas",
    icon="📄"
)

pg = st.navigation(
    {
        "Mercado Público": [
            buscador_page
        ],
        "Herramientas": [
            fichas_page
        ]
    }
)

pg.run()