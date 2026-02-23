"""
Cliente HTTP base para a API da Conta Azul.
Gerencia autenticação, headers e rate limiting.
"""

import time

import requests

from auth import ContaAzulAuth

API_BASE_URL = "https://api-v2.contaazul.com/v1"

# Rate limits: 600 req/min, 10 req/s
MIN_REQUEST_INTERVAL = 0.1  # 100ms entre requests


class ContaAzulClient:
    def __init__(self, auth: ContaAzulAuth = None):
        self.auth = auth or ContaAzulAuth()
        self.session = requests.Session()
        self._last_request_time = 0

    def _get_headers(self):
        token = self.auth.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _throttle(self):
        """Respeita o rate limit de 10 req/s."""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def _request(self, method, path, **kwargs):
        """Executa uma requisição autenticada à API."""
        self._throttle()
        url = f"{API_BASE_URL}{path}"
        response = self.session.request(
            method, url, headers=self._get_headers(), **kwargs
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def post(self, path, data=None):
        return self._request("POST", path, json=data)

    def put(self, path, data=None):
        return self._request("PUT", path, json=data)

    def delete(self, path):
        return self._request("DELETE", path)
