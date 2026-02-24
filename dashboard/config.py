"""
Configuração centralizada do dashboard.
Carrega variáveis de ambiente (.env local) ou st.secrets (Streamlit Cloud).
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Carrega .env a partir da raiz do projeto (apenas local)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(PROJECT_ROOT / ".env")


def _get_secret(key: str, default: str = None) -> str | None:
    """Busca config em st.secrets (Cloud) ou os.environ (.env local)."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


# ─── OAuth2 ───

CLIENT_ID = _get_secret("CONTA_AZUL_CLIENT_ID")
CLIENT_SECRET = _get_secret("CONTA_AZUL_CLIENT_SECRET")
REDIRECT_URI = _get_secret("CONTA_AZUL_REDIRECT_URI", "https://contaazul.com")
STATE = _get_secret("CONTA_AZUL_STATE", "random_state")
REFRESH_TOKEN = _get_secret("CONTA_AZUL_REFRESH_TOKEN")

AUTH_URL = "https://auth.contaazul.com/login"
TOKEN_URL = "https://auth.contaazul.com/oauth2/token"
TOKEN_FILE = str(PROJECT_ROOT / "token.json")
SCOPE = ""  # Conta Azul não requer scope explícito

# ─── API ───

API_BASE_URL = "https://api-v2.contaazul.com/v1"
MIN_REQUEST_INTERVAL = 0.1  # 100ms (respeita 10 req/s)
MAX_RETRIES = 3
RETRY_BACKOFF = 1.0  # segundos

# ─── Cache ───

CACHE_TTL = 300  # 5 minutos

# ─── Dashboard ───

PROJECTION_DAYS = 60
BURN_RATE_MONTHS = 6
LOOKBACK_DAYS = 180
DELINQUENCY_WARNING_THRESHOLD = 0.20  # 20%
