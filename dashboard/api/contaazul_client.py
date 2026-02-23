"""
Cliente HTTP para a API Conta Azul v2.

Responsabilidades:
- Autenticação automática (Bearer token)
- Rate limiting (100ms entre requests)
- Retry com backoff exponencial
- Paginação automática
- Endpoints financeiros tipados
"""

import time
from datetime import date, timedelta

import requests

from dashboard.api.auth import ContaAzulAuth
from dashboard.config import (
    API_BASE_URL,
    MIN_REQUEST_INTERVAL,
    MAX_RETRIES,
    RETRY_BACKOFF,
    LOOKBACK_DAYS,
)


class ContaAzulClient:
    """Cliente de baixo nível para a API REST."""

    def __init__(self, auth: ContaAzulAuth = None):
        self.auth = auth or ContaAzulAuth()
        self.session = requests.Session()
        self._last_request_time = 0.0

    # ─── HTTP primitivos ───

    def _get_headers(self) -> dict:
        token = self.auth.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def _request(self, method: str, path: str, **kwargs) -> dict | list | None:
        last_error = None
        for attempt in range(MAX_RETRIES):
            self._throttle()
            try:
                url = f"{API_BASE_URL}{path}"
                resp = self.session.request(
                    method, url, headers=self._get_headers(), **kwargs
                )
                resp.raise_for_status()
                if resp.status_code == 204 or not resp.content:
                    return None
                return resp.json()
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                # 401 → token expirou, tenta refresh
                if status == 401 and attempt == 0:
                    try:
                        self.auth._refresh()
                        continue
                    except Exception:
                        pass
                # 429 / 5xx → retry com backoff
                if status in (429, 500, 502, 503, 504):
                    last_error = e
                    time.sleep(RETRY_BACKOFF * (2 ** attempt))
                    continue
                raise
            except requests.exceptions.ConnectionError as e:
                last_error = e
                time.sleep(RETRY_BACKOFF * (2 ** attempt))
                continue

        raise last_error

    def get(self, path: str, params: dict = None):
        return self._request("GET", path, params=params)

    def post(self, path: str, data: dict = None):
        return self._request("POST", path, json=data)

    # ─── Paginação ───

    def fetch_all_pages(
        self,
        path: str,
        params: dict = None,
        page_size: int = 50,
    ) -> list:
        """Busca todas as páginas de um endpoint paginado."""
        params = dict(params or {})
        params["tamanho_pagina"] = page_size
        all_items = []
        page = 1

        while True:
            params["pagina"] = page
            result = self.get(path, params=params)

            if result is None:
                break

            # Suporta resposta paginada {itens, itens_totais} ou lista direta
            if isinstance(result, dict):
                items = result.get("itens", [])
                total = result.get("itens_totais", 0)
            elif isinstance(result, list):
                items = result
                total = len(items)
            else:
                break

            all_items.extend(items)

            if len(all_items) >= total or not items:
                break
            page += 1

        return all_items

    # ─── Endpoints financeiros (alto nível) ───

    def get_cash_accounts(self) -> list:
        """Retorna todas as contas financeiras (bancárias, aplicações, cartões)."""
        return self.fetch_all_pages("/conta-financeira")

    def get_account_balance(self, account_id: str) -> dict:
        """Retorna saldo atual de uma conta financeira."""
        return self.get(f"/conta-financeira/{account_id}/saldo-atual")

    def get_receivables(
        self,
        date_from: str = None,
        date_to: str = None,
    ) -> list:
        """Retorna todas as contas a receber no período."""
        today = date.today()
        date_from = date_from or (today - timedelta(days=LOOKBACK_DAYS)).isoformat()
        date_to = date_to or (today + timedelta(days=LOOKBACK_DAYS)).isoformat()
        return self.fetch_all_pages(
            "/financeiro/eventos-financeiros/contas-a-receber/buscar",
            params={
                "data_vencimento_de": date_from,
                "data_vencimento_ate": date_to,
            },
        )

    def get_payables(
        self,
        date_from: str = None,
        date_to: str = None,
    ) -> list:
        """Retorna todas as contas a pagar no período."""
        today = date.today()
        date_from = date_from or (today - timedelta(days=LOOKBACK_DAYS)).isoformat()
        date_to = date_to or (today + timedelta(days=LOOKBACK_DAYS)).isoformat()
        return self.fetch_all_pages(
            "/financeiro/eventos-financeiros/contas-a-pagar/buscar",
            params={
                "data_vencimento_de": date_from,
                "data_vencimento_ate": date_to,
            },
        )

    def get_categories(self) -> list:
        """Retorna todas as categorias financeiras."""
        return self.fetch_all_pages("/categorias")

    def get_cash_balance(self) -> dict:
        """
        Retorna posição de caixa consolidada:
        {total, contas: [{nome, tipo, saldo, ativo}]}
        """
        accounts = self.get_cash_accounts()
        result = {"total": 0.0, "contas": []}

        for acc in accounts:
            if not acc.get("ativo", True):
                continue

            try:
                bal = self.get_account_balance(acc["id"])
                saldo = (bal or {}).get("saldo_atual", 0.0) or 0.0
            except Exception:
                saldo = 0.0

            result["contas"].append({
                "id": acc.get("id"),
                "nome": acc.get("nome", "Conta sem nome"),
                "tipo": acc.get("tipo", ""),
                "banco": acc.get("banco", ""),
                "saldo": saldo,
            })
            result["total"] += saldo

        return result
