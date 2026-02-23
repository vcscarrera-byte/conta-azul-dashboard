"""
Autenticação OAuth2 com AWS Cognito para a API Conta Azul.

Gerencia:
- Armazenamento de refresh_token
- Expiração de tokens
- Refresh automático
- Sem passos manuais em runtime
"""

import base64
import json
import os
import time
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from dashboard.config import (
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    REFRESH_TOKEN,
    STATE,
    AUTH_URL,
    TOKEN_URL,
    TOKEN_FILE,
    SCOPE,
)


class ContaAzulAuth:
    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        redirect_uri: str = None,
    ):
        self.client_id = client_id or CLIENT_ID
        self.client_secret = client_secret or CLIENT_SECRET
        self.redirect_uri = redirect_uri or REDIRECT_URI

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "client_id e client_secret são obrigatórios. "
                "Defina CONTA_AZUL_CLIENT_ID e CONTA_AZUL_CLIENT_SECRET no .env ou st.secrets"
            )

        self.access_token: str | None = None
        self.refresh_token: str | None = REFRESH_TOKEN  # Pode vir do secrets (Cloud)
        self.expires_at: float = 0

    # ─── Header de autenticação Basic ───

    def _basic_auth_header(self) -> str:
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    # ─── Obter token válido (entry point principal) ───

    def get_access_token(self) -> str:
        """Retorna access_token válido, renovando automaticamente se necessário."""
        # Token em memória ainda válido
        if self.access_token and time.time() < self.expires_at:
            return self.access_token

        # Tem refresh_token em memória → renova
        if self.refresh_token:
            self._refresh()
            return self.access_token

        # Tenta carregar do arquivo
        if self._load_token():
            if time.time() < self.expires_at:
                return self.access_token
            if self.refresh_token:
                self._refresh()
                return self.access_token

        raise ValueError(
            "Nenhum token disponível. Execute o fluxo de autorização primeiro:\n"
            "  python -m dashboard.api.auth"
        )

    # ─── Fluxos OAuth2 ───

    def get_authorization_url(self) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": STATE,
            "scope": SCOPE,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict:
        """Troca authorization code por access_token + refresh_token."""
        headers = {
            "Authorization": self._basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        response = requests.post(TOKEN_URL, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()
        self._save_token(token_data)
        return token_data

    def _refresh(self):
        """Renova o access_token usando o refresh_token."""
        if not self.refresh_token:
            raise ValueError("Nenhum refresh_token disponível.")

        headers = {
            "Authorization": self._basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        response = requests.post(TOKEN_URL, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()
        self._save_token(token_data)

    # ─── Persistência ───

    def _save_token(self, token_data: dict):
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token", self.refresh_token)
        expires_in = token_data.get("expires_in", 3600)
        self.expires_at = time.time() + expires_in - 60  # margem de 60s

        try:
            with open(TOKEN_FILE, "w") as f:
                json.dump(
                    {
                        "access_token": self.access_token,
                        "refresh_token": self.refresh_token,
                        "expires_at": self.expires_at,
                    },
                    f,
                )
        except OSError:
            # No Cloud (read-only filesystem), salva apenas em memória
            pass

    def _load_token(self) -> bool:
        if not os.path.exists(TOKEN_FILE):
            return False
        with open(TOKEN_FILE) as f:
            data = json.load(f)
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        self.expires_at = data.get("expires_at", 0)
        return True

    # ─── Fluxo interativo (CLI) ───

    def authorize_interactive(self) -> dict:
        auth_url = self.get_authorization_url()
        print("Abrindo navegador para autorização...")
        print(f"Se não abrir automaticamente, acesse:\n{auth_url}\n")
        webbrowser.open(auth_url)

        print("Após autorizar, copie a URL completa e cole aqui.\n")
        user_input = input("Cole a URL ou o code aqui: ").strip()

        if "code=" in user_input:
            parsed = urlparse(user_input)
            query = parse_qs(parsed.query)
            code = query.get("code", [None])[0]
        else:
            code = user_input

        if not code:
            raise ValueError("Não foi possível obter o authorization code.")

        token_data = self.exchange_code(code)
        print("Token obtido com sucesso!")
        return token_data


# ─── CLI entry point ───

if __name__ == "__main__":
    auth = ContaAzulAuth()
    auth.authorize_interactive()
