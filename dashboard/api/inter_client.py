"""
Cliente HTTP para a Banking API v2 do Banco Inter PJ.

Responsabilidades:
- Autenticação mTLS (certificado em todas as requisições)
- Bearer token OAuth2
- Rate limiting e retry com backoff
- Endpoints: saldo e extrato
"""

import time
from datetime import date, timedelta

import requests

from dashboard.api.inter_auth import InterAuth
from dashboard.config import (
    INTER_API_BASE_URL,
    INTER_CONTA_CORRENTE,
    MIN_REQUEST_INTERVAL,
    MAX_RETRIES,
    RETRY_BACKOFF,
)
from dashboard.models.inter_models import InterBalance, InterTransaction


class InterClient:
    """Cliente para a Banking API v2 do Banco Inter."""

    def __init__(self, auth: InterAuth = None):
        self.auth = auth or InterAuth()
        self.session = requests.Session()
        self.session.cert = self.auth.cert
        self._last_request_time = 0.0

    # ─── HTTP primitivos ───

    def _get_headers(self) -> dict:
        token = self.auth.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if INTER_CONTA_CORRENTE:
            headers["x-conta-corrente"] = INTER_CONTA_CORRENTE
        return headers

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
                url = f"{INTER_API_BASE_URL}{path}"
                resp = self.session.request(
                    method, url, headers=self._get_headers(), **kwargs
                )
                resp.raise_for_status()
                if resp.status_code == 204 or not resp.content:
                    return None
                return resp.json()
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if status == 401 and attempt == 0:
                    try:
                        self.auth._request_token()
                        continue
                    except Exception:
                        pass
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

    # ─── Endpoints Banking v2 ───

    def get_balance(self) -> InterBalance:
        """Retorna saldo da conta corrente."""
        data = self.get("/banking/v2/saldo")
        if not data:
            return InterBalance()
        return InterBalance(
            disponivel=float(data.get("disponivel", 0)),
            bloqueado_cheque=float(data.get("bloqueadoCheque", 0)),
            bloqueado_judicial=float(data.get("bloqueadoJuridico", 0)),
            limite=float(data.get("limite", 0)),
        )

    def get_statement(
        self,
        date_from: str = None,
        date_to: str = None,
    ) -> list[InterTransaction]:
        """
        Retorna extrato bancário.
        Limite da API: máximo 90 dias por consulta.
        """
        today = date.today()
        date_from = date_from or (today - timedelta(days=30)).strftime("%Y-%m-%d")
        date_to = date_to or today.strftime("%Y-%m-%d")

        data = self.get("/banking/v2/extrato", params={
            "dataInicio": date_from,
            "dataFim": date_to,
        })

        if not data:
            return []

        # A API retorna {"transacoes": [...]} ou lista direta
        transactions_raw = data.get("transacoes", data) if isinstance(data, dict) else data
        if not isinstance(transactions_raw, list):
            return []

        transactions = []
        for tx in transactions_raw:
            try:
                tx_date = date.fromisoformat(tx.get("dataEntrada", tx.get("dataMovimento", ""))[:10])
            except (ValueError, TypeError):
                continue

            tipo = tx.get("tipoOperacao", tx.get("tipo", "")).upper()
            if tipo not in ("CREDITO", "DEBITO", "C", "D"):
                tipo = "DEBITO" if float(tx.get("valor", 0)) < 0 else "CREDITO"

            # Normalizar tipo
            if tipo == "C":
                tipo = "CREDITO"
            elif tipo == "D":
                tipo = "DEBITO"

            transactions.append(InterTransaction(
                data=tx_date,
                tipo=tipo,
                descricao=tx.get("descricao", tx.get("titulo", "")),
                valor=abs(float(tx.get("valor", 0))),
                titulo=tx.get("titulo", ""),
                numero_documento=tx.get("numeroDocumento", ""),
            ))

        return transactions
