"""
Camada de dados do Dashboard CFO.
Agrega e processa dados da API Conta Azul para os widgets do dashboard.
"""

import pandas as pd
from datetime import date, timedelta

from auth import ContaAzulAuth
from client import ContaAzulClient
from financeiro import Financeiro


def format_brl(value):
    """Formata um número como Real brasileiro (R$ 150.000,50)."""
    if value >= 0:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class DashboardData:
    def __init__(self):
        auth = ContaAzulAuth()
        client = ContaAzulClient(auth)
        self.fin = Financeiro(client)

        # Caches internos (busca 1x, reutiliza)
        self._receivables = None
        self._payables = None
        self._categories = None

    # ─── Helpers ───

    def _fetch_all_pages(self, method, **kwargs):
        """Busca todas as páginas de um endpoint paginado."""
        all_items = []
        page = 1
        page_size = 50
        while True:
            result = method(pagina=page, tamanho_pagina=page_size, **kwargs)
            items = result.get("itens", [])
            all_items.extend(items)
            total = result.get("itens_totais", 0)
            if len(all_items) >= total or not items:
                break
            page += 1
        return all_items

    def _get_all_receivables(self):
        """Retorna todos os recebimentos (cache interno)."""
        if self._receivables is None:
            today = date.today()
            date_from = (today - timedelta(days=180)).isoformat()
            date_to = (today + timedelta(days=180)).isoformat()
            self._receivables = self._fetch_all_pages(
                self.fin.listar_recebimentos,
                data_vencimento_de=date_from,
                data_vencimento_ate=date_to,
            )
        return self._receivables

    def _get_all_payables(self):
        """Retorna todos os pagamentos (cache interno)."""
        if self._payables is None:
            today = date.today()
            date_from = (today - timedelta(days=180)).isoformat()
            date_to = (today + timedelta(days=180)).isoformat()
            self._payables = self._fetch_all_pages(
                self.fin.listar_pagamentos,
                data_vencimento_de=date_from,
                data_vencimento_ate=date_to,
            )
        return self._payables

    def _get_all_categories(self):
        """Retorna todas as categorias (cache interno)."""
        if self._categories is None:
            self._categories = self._fetch_all_pages(self.fin.listar_categorias)
        return self._categories

    def _classify_bucket(self, data_vencimento_str):
        """Classifica uma data de vencimento em bucket de aging."""
        today = date.today()
        try:
            dt = date.fromisoformat(data_vencimento_str)
        except (ValueError, TypeError):
            return "Outros"

        diff = (dt - today).days
        if diff < 0:
            return "Vencido"
        elif diff <= 30:
            return "0-30d"
        elif diff <= 60:
            return "31-60d"
        else:
            return "60+d"

    # ─── Widgets ───

    def get_cash_position(self):
        """Widget 1: Posição de caixa total e por conta."""
        contas = self._fetch_all_pages(self.fin.listar_contas_financeiras)
        result = {"total": 0.0, "contas": []}

        for conta in contas:
            # Ignorar contas inativas
            if not conta.get("ativo", True):
                continue

            try:
                saldo_resp = self.fin.obter_saldo_conta(conta["id"])
                saldo = saldo_resp.get("saldo_atual", saldo_resp.get("saldo", 0.0)) if saldo_resp else 0.0
            except Exception:
                saldo = 0.0

            result["contas"].append({
                "nome": conta.get("nome", "Conta sem nome"),
                "tipo": conta.get("tipo", ""),
                "saldo": saldo,
            })
            result["total"] += saldo

        return result

    def get_receivables_aging(self):
        """Widget 5: Contas a receber agrupadas por aging bucket."""
        items = self._get_all_receivables()

        buckets = {"Vencido": 0.0, "0-30d": 0.0, "31-60d": 0.0, "60+d": 0.0}
        counts = {"Vencido": 0, "0-30d": 0, "31-60d": 0, "60+d": 0}

        for item in items:
            # Ignorar quitados/cancelados
            status = (item.get("status", "") or "").upper()
            if status in ("PAID", "CANCELLED", "CANCELED"):
                continue

            nao_pago = item.get("nao_pago", item.get("total", 0)) or 0
            if nao_pago <= 0:
                continue

            bucket = self._classify_bucket(item.get("data_vencimento"))
            if bucket in buckets:
                buckets[bucket] += nao_pago
                counts[bucket] += 1

        order = ["Vencido", "0-30d", "31-60d", "60+d"]
        df = pd.DataFrame({
            "bucket": order,
            "valor_total": [buckets[b] for b in order],
            "quantidade": [counts[b] for b in order],
        })
        return df

    def get_payables_aging(self):
        """Widget 6: Contas a pagar agrupadas por aging bucket."""
        items = self._get_all_payables()

        buckets = {"Vencido": 0.0, "0-30d": 0.0, "31-60d": 0.0, "60+d": 0.0}
        counts = {"Vencido": 0, "0-30d": 0, "31-60d": 0, "60+d": 0}

        for item in items:
            status = (item.get("status", "") or "").upper()
            if status in ("PAID", "CANCELLED", "CANCELED"):
                continue

            nao_pago = item.get("nao_pago", item.get("total", 0)) or 0
            if nao_pago <= 0:
                continue

            bucket = self._classify_bucket(item.get("data_vencimento"))
            if bucket in buckets:
                buckets[bucket] += nao_pago
                counts[bucket] += 1

        order = ["Vencido", "0-30d", "31-60d", "60+d"]
        df = pd.DataFrame({
            "bucket": order,
            "valor_total": [buckets[b] for b in order],
            "quantidade": [counts[b] for b in order],
        })
        return df

    def get_monthly_revenue_expenses(self, months=6):
        """Widget 7: Receita vs Despesa mensal (últimos N meses)."""
        today = date.today()
        start = (today.replace(day=1) - timedelta(days=months * 30)).replace(day=1)

        receivables = self._get_all_receivables()
        payables = self._get_all_payables()

        # Montar meses
        month_labels = []
        current = start
        while current <= today:
            month_labels.append(current.strftime("%Y-%m"))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        receita = {m: 0.0 for m in month_labels}
        despesa = {m: 0.0 for m in month_labels}

        # Receita = recebimentos com valor pago > 0
        for item in receivables:
            pago = item.get("pago", 0) or 0
            if pago <= 0:
                continue
            dt_str = item.get("data_competencia", item.get("data_vencimento", ""))
            if dt_str:
                month_key = dt_str[:7]  # YYYY-MM
                if month_key in receita:
                    receita[month_key] += pago

        # Despesa = pagamentos com valor pago > 0
        for item in payables:
            pago = item.get("pago", 0) or 0
            if pago <= 0:
                continue
            dt_str = item.get("data_competencia", item.get("data_vencimento", ""))
            if dt_str:
                month_key = dt_str[:7]
                if month_key in despesa:
                    despesa[month_key] += pago

        # Converter para nomes de meses em pt-BR
        month_names = {
            "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
            "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
            "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
        }

        rows = []
        for m in month_labels:
            mm = m.split("-")[1]
            label = f"{month_names.get(mm, mm)}/{m[:4]}"
            r = receita[m]
            d = despesa[m]
            rows.append({
                "mes": label,
                "receita": r,
                "despesa": d,
                "resultado": r - d,
            })

        return pd.DataFrame(rows)

    def get_expense_breakdown(self):
        """Widget 8: Despesas por categoria (mês corrente)."""
        today = date.today()
        start = today.replace(day=1).isoformat()
        end = today.isoformat()

        try:
            payables = self._fetch_all_pages(
                self.fin.listar_pagamentos,
                data_vencimento_de=start,
                data_vencimento_ate=end,
            )
        except Exception:
            payables = self._get_all_payables()

        cat_totals = {}
        for item in payables:
            valor = item.get("total", 0) or 0
            if valor <= 0:
                continue

            categorias = item.get("categorias", [])
            if categorias:
                cat_name = categorias[0].get("nome", "Sem categoria")
            else:
                cat_name = "Sem categoria"

            cat_totals[cat_name] = cat_totals.get(cat_name, 0) + valor

        if not cat_totals:
            return pd.DataFrame({"categoria": ["Sem dados"], "valor": [0], "percentual": [0]})

        # Top 8 + Outros
        sorted_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
        top = sorted_cats[:8]
        others_sum = sum(v for _, v in sorted_cats[8:])

        rows = [{"categoria": name, "valor": val} for name, val in top]
        if others_sum > 0:
            rows.append({"categoria": "Outros", "valor": others_sum})

        total = sum(r["valor"] for r in rows)
        for r in rows:
            r["percentual"] = (r["valor"] / total * 100) if total > 0 else 0

        return pd.DataFrame(rows)

    def get_liquidity_ratios(self):
        """Widgets 2-4: Indicadores de liquidez."""
        cash = self.get_cash_position()
        receivables_df = self.get_receivables_aging()
        payables_df = self.get_payables_aging()

        total_cash = cash["total"]

        # Ativo corrente = caixa + recebíveis (todos os buckets)
        total_receivables = receivables_df["valor_total"].sum()
        current_assets = total_cash + total_receivables

        # Passivo corrente = todas as contas a pagar pendentes
        total_payables = payables_df["valor_total"].sum()

        # Recebíveis curto prazo (0-30d)
        rec_30d = receivables_df.loc[
            receivables_df["bucket"] == "0-30d", "valor_total"
        ].sum()

        # Payables curto prazo (vencido + 0-30d)
        pay_short = payables_df.loc[
            payables_df["bucket"].isin(["Vencido", "0-30d"]), "valor_total"
        ].sum()

        return {
            "quick_ratio": (total_cash + rec_30d) / pay_short if pay_short > 0 else 0,
            "current_ratio": current_assets / total_payables if total_payables > 0 else 0,
            "working_capital": current_assets - total_payables,
            "total_cash": total_cash,
            "total_receivables": total_receivables,
            "total_payables": total_payables,
        }
