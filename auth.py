"""
Módulo de autenticação OAuth2 para a API da Conta Azul.

Fluxo OAuth2 Authorization Code:
1. Redirecionar usuário para URL de autorização (auth.contaazul.com)
2. Capturar o code retornado no callback
3. Trocar o code por access_token e refresh_token
4. Renovar o token a cada 60 minutos usando refresh_token
"""

import base64
import json
import os
import time
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from dotenv import load_dotenv

load_dotenv()

AUTH_URL = "https://auth.contaazul.com/login"
TOKEN_URL = "https://auth.contaazul.com/oauth2/token"
TOKEN_FILE = "token.json"
SCOPE = "openid+profile+aws.cognito.signin.user.admin"


class ContaAzulAuth:
    def __init__(
        self,
        client_id=None,
        client_secret=None,
        redirect_uri=None,
        state=None,
    ):
        self.client_id = client_id or os.getenv("CONTA_AZUL_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("CONTA_AZUL_CLIENT_SECRET")
        self.redirect_uri = redirect_uri or os.getenv(
            "CONTA_AZUL_REDIRECT_URI", "https://www.contaazul.com"
        )
        self.state = state or os.getenv("CONTA_AZUL_STATE", "random_state")

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "client_id e client_secret são obrigatórios. "
                "Defina via parâmetro ou nas variáveis de ambiente "
                "CONTA_AZUL_CLIENT_ID e CONTA_AZUL_CLIENT_SECRET."
            )

        self.access_token = None
        self.refresh_token = None
        self.expires_at = 0

    def _basic_auth_header(self):
        """Gera o header Authorization Basic com client_id:client_secret em Base64."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def get_authorization_url(self):
        """Retorna a URL para redirecionar o usuário para autorização."""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": self.state,
            "scope": SCOPE,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code):
        """Troca o authorization code por access_token e refresh_token."""
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

    def refresh(self):
        """Renova o access_token usando o refresh_token."""
        if not self.refresh_token:
            raise ValueError("Nenhum refresh_token disponível. Faça login novamente.")

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
        return token_data

    def get_access_token(self):
        """Retorna um access_token válido, renovando se necessário."""
        if self.access_token and time.time() < self.expires_at:
            return self.access_token

        if self.refresh_token:
            self.refresh()
            return self.access_token

        # Tenta carregar do arquivo
        if self._load_token():
            if time.time() < self.expires_at:
                return self.access_token
            if self.refresh_token:
                self.refresh()
                return self.access_token

        raise ValueError(
            "Nenhum token disponível. Execute o fluxo de autorização primeiro."
        )

    def _save_token(self, token_data):
        """Salva os tokens em memória e em arquivo."""
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token", self.refresh_token)
        expires_in = token_data.get("expires_in", 3600)
        self.expires_at = time.time() + expires_in - 60  # margem de 60s

        with open(TOKEN_FILE, "w") as f:
            json.dump(
                {
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "expires_at": self.expires_at,
                },
                f,
            )

    def _load_token(self):
        """Carrega tokens salvos do arquivo."""
        if not os.path.exists(TOKEN_FILE):
            return False
        with open(TOKEN_FILE) as f:
            data = json.load(f)
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        self.expires_at = data.get("expires_at", 0)
        return True

    def authorize_interactive(self):
        """
        Inicia o fluxo OAuth2:
        1. Abre o navegador para o usuário autorizar
        2. Após autorizar, o usuário é redirecionado para a redirect_uri
           com o ?code=XXX na URL
        3. O usuário cola a URL ou o code no terminal
        4. Troca o code pelo token
        """
        auth_url = self.get_authorization_url()
        print("Abrindo navegador para autorização...")
        print(f"Se não abrir automaticamente, acesse:\n{auth_url}\n")
        webbrowser.open(auth_url)

        print("Após autorizar, você será redirecionado para uma página.")
        print("Copie a URL completa da barra de endereço e cole aqui.\n")
        print("(A URL vai conter algo como ?code=XXXXXXX)\n")

        user_input = input("Cole a URL ou o code aqui: ").strip()

        # Extrai o code da URL ou usa direto se for só o code
        if "code=" in user_input:
            parsed = urlparse(user_input)
            query = parse_qs(parsed.query)
            if "code" not in query:
                raise ValueError("URL não contém o parâmetro 'code'.")
            code = query["code"][0]
        else:
            code = user_input

        if not code:
            raise ValueError("Não foi possível obter o authorization code.")

        print("Code recebido! Trocando por token...")
        token_data = self.exchange_code(code)
        print("Token obtido com sucesso!")
        return token_data
