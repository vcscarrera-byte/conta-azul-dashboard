"""
Autenticação mTLS + OAuth2 Client Credentials para o Banco Inter PJ.

Gerencia:
- Certificado digital (mTLS) em todas as requisições
- Token OAuth2 via Client Credentials
- Cache de token com auto-renovação (expira em 1h)
- Suporte a certificado via arquivo ou base64 (Cloud)
"""

import base64
import json
import os
import tempfile
import time

import requests

from dashboard.config import (
    INTER_CLIENT_ID,
    INTER_CLIENT_SECRET,
    INTER_CERT_PATH,
    INTER_KEY_PATH,
    INTER_TOKEN_URL,
    PROJECT_ROOT,
)


def _get_cached_token() -> dict | None:
    """Recupera token do st.session_state."""
    try:
        import streamlit as st
        return st.session_state.get("_inter_token")
    except Exception:
        return None


def _set_cached_token(token_data: dict):
    """Salva token no st.session_state."""
    try:
        import streamlit as st
        st.session_state["_inter_token"] = token_data
    except Exception:
        pass


def _resolve_cert_path(path: str | None) -> str | None:
    """Resolve caminho do certificado (absoluto ou relativo à raiz do projeto)."""
    if not path:
        return None
    if os.path.isabs(path):
        return path
    resolved = os.path.join(str(PROJECT_ROOT), path)
    if os.path.exists(resolved):
        return resolved
    return path


def _decode_base64_cert(b64_content: str) -> str:
    """Decodifica certificado base64 para arquivo temporário (para Streamlit Cloud)."""
    content = base64.b64decode(b64_content)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    tmp.write(content)
    tmp.close()
    return tmp.name


class InterAuth:
    """Gerenciador de autenticação mTLS + OAuth2 para o Banco Inter."""

    TOKEN_FILE = os.path.join(str(PROJECT_ROOT), "inter_token.json")

    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        cert_path: str = None,
        key_path: str = None,
    ):
        self.client_id = client_id or INTER_CLIENT_ID
        self.client_secret = client_secret or INTER_CLIENT_SECRET

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "INTER_CLIENT_ID e INTER_CLIENT_SECRET são obrigatórios. "
                "Configure no .env ou st.secrets."
            )

        # Resolver caminhos dos certificados
        raw_cert = cert_path or INTER_CERT_PATH
        raw_key = key_path or INTER_KEY_PATH

        # Suporte a base64 (para Streamlit Cloud)
        if raw_cert and raw_cert.startswith("base64:"):
            self.cert_path = _decode_base64_cert(raw_cert[7:])
        else:
            self.cert_path = _resolve_cert_path(raw_cert)

        if raw_key and raw_key.startswith("base64:"):
            self.key_path = _decode_base64_cert(raw_key[7:])
        else:
            self.key_path = _resolve_cert_path(raw_key)

        if not self.cert_path or not self.key_path:
            raise ValueError(
                "INTER_CERT_PATH e INTER_KEY_PATH são obrigatórios. "
                "Baixe o certificado no Internet Banking PJ do Inter."
            )

        self.access_token: str | None = None
        self.expires_at: float = 0

        # Carregar token: session_state > arquivo
        cached = _get_cached_token()
        if cached:
            self.access_token = cached.get("access_token")
            self.expires_at = cached.get("expires_at", 0)
        else:
            self._load_token()

    @property
    def cert(self) -> tuple[str, str]:
        """Par (cert, key) para usar no requests."""
        return (self.cert_path, self.key_path)

    def get_access_token(self) -> str:
        """Retorna access_token válido, renovando se necessário."""
        if self.access_token and time.time() < self.expires_at:
            return self.access_token

        self._request_token()
        return self.access_token

    def _request_token(self):
        """Solicita novo token via OAuth2 Client Credentials com mTLS."""
        response = requests.post(
            INTER_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "extrato.read",
            },
            cert=self.cert,
        )
        if not response.ok:
            error_detail = response.text[:500]
            raise RuntimeError(
                f"Falha ao obter token do Inter ({response.status_code}): {error_detail}"
            )

        token_data = response.json()
        self._save_token(token_data)

    def _save_token(self, token_data: dict):
        self.access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self.expires_at = time.time() + expires_in - 60  # margem de 60s

        token_cache = {
            "access_token": self.access_token,
            "expires_at": self.expires_at,
        }

        _set_cached_token(token_cache)

        try:
            with open(self.TOKEN_FILE, "w") as f:
                json.dump(token_cache, f)
        except OSError:
            pass

    def _load_token(self) -> bool:
        if not os.path.exists(self.TOKEN_FILE):
            return False
        try:
            with open(self.TOKEN_FILE) as f:
                data = json.load(f)
            self.access_token = data.get("access_token")
            self.expires_at = data.get("expires_at", 0)
            return True
        except (json.JSONDecodeError, OSError):
            return False
