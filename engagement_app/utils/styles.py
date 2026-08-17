import streamlit as st

def cargar_css():
    with open("engagement_app/styles.css") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )