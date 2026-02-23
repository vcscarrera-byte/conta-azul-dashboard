"""
Utilitários de cache para o dashboard.
Fornece decoradores e helpers para evitar chamadas duplicadas à API.
"""

import streamlit as st
from dashboard.config import CACHE_TTL


def cached(ttl: int = CACHE_TTL):
    """Decorador wrapper em torno de st.cache_data para uso fora do Streamlit."""
    return st.cache_data(ttl=ttl, show_spinner=False)


def clear_all_caches():
    """Limpa todos os caches do Streamlit."""
    st.cache_data.clear()
