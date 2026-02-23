"""
Serviço de Métricas Financeiras.

Responsabilidades:
- Burn Rate
- Runway
- Inadimplência (Delinquency)
- Posição Líquida (Net Position)
- Indicadores de liquidez
"""

from datetime import date, timedelta

from dashboard.models.financial_models import (
    BurnRate,
    Runway,
    Delinquency,
    NetPosition,
)
from dashboard.config import BURN_RATE_MONTHS


# ─── Burn Rate ───

def calculate_burn_rate(
    payables: list[dict],
    months: int = BURN_RATE_MONTHS,
) -> BurnRate:
    """
    Calcula a taxa de queima mensal média.

    Usa pagamentos efetuados (valor pago > 0) nos últimos N meses.
    """
    today = date.today()

    # Gerar meses
    month_keys = []
    current = today.replace(day=1)
    for _ in range(months):
        month_keys.append(current.strftime("%Y-%m"))
        current = (current - timedelta(days=1)).replace(day=1)

    monthly_expenses: dict[str, float] = {mk: 0.0 for mk in month_keys}

    for item in payables:
        pago = float(item.get("pago", 0) or 0)
        if pago <= 0:
            continue

        dt_str = item.get("data_competencia", item.get("data_vencimento", ""))
        if not dt_str:
            continue

        mk = dt_str[:7]
        if mk in monthly_expenses:
            monthly_expenses[mk] += pago

    # Calcular média (ignorar meses com 0 se forem futuros/sem dados)
    current_month = today.strftime("%Y-%m")
    active_months = [
        (mk, v) for mk, v in monthly_expenses.items()
        if v > 0 and mk != current_month  # exclui mês atual (incompleto)
    ]

    if not active_months:
        # Incluir mês atual se for o único
        active_months = [
            (mk, v) for mk, v in monthly_expenses.items() if v > 0
        ]

    total = sum(v for _, v in active_months)
    count = max(len(active_months), 1)

    breakdown = [
        {"month": mk, "expense": v}
        for mk, v in sorted(monthly_expenses.items())
        if v > 0
    ]

    return BurnRate(
        monthly_average=total / count,
        months_used=count,
        monthly_breakdown=breakdown,
    )


# ─── Runway ───

def calculate_runway(cash: float, burn_rate: float) -> Runway:
    """
    Calcula meses de operação restantes.

    runway_months = cash / burn_rate
    """
    if burn_rate <= 0:
        return Runway(months=float("inf"), is_infinite=True)

    months = cash / burn_rate
    return Runway(months=max(months, 0), is_infinite=False)


# ─── Delinquency (Inadimplência) ───

def calculate_delinquency(receivables: list[dict]) -> Delinquency:
    """
    Calcula taxa de inadimplência.

    Critério: vencimento < hoje E status != pago
    """
    today = date.today()

    total_receivable = 0.0
    overdue_receivable = 0.0
    overdue_count = 0
    total_count = 0

    for item in receivables:
        status = (item.get("status") or "").upper()
        if status in ("CANCELLED", "CANCELED"):
            continue

        amount = float(item.get("nao_pago", item.get("total", 0)) or 0)
        if amount <= 0:
            continue

        total_receivable += amount
        total_count += 1

        if status not in ("PAID",):
            due_str = item.get("data_vencimento", "")
            if due_str:
                try:
                    due_date = date.fromisoformat(due_str[:10])
                    if due_date < today:
                        overdue_receivable += amount
                        overdue_count += 1
                except (ValueError, TypeError):
                    pass

    rate = (overdue_receivable / total_receivable * 100) if total_receivable > 0 else 0

    return Delinquency(
        total_receivable=total_receivable,
        overdue_receivable=overdue_receivable,
        delinquency_rate=rate,
        overdue_count=overdue_count,
        total_count=total_count,
    )


# ─── Net Position ───

def calculate_net_position(
    receivables: list[dict],
    payables: list[dict],
) -> NetPosition:
    """
    Calcula posição líquida: recebíveis pendentes − pagáveis pendentes.
    """
    recv_total = 0.0
    for item in receivables:
        status = (item.get("status") or "").upper()
        if status in ("PAID", "CANCELLED", "CANCELED"):
            continue
        recv_total += float(item.get("nao_pago", item.get("total", 0)) or 0)

    pay_total = 0.0
    for item in payables:
        status = (item.get("status") or "").upper()
        if status in ("PAID", "CANCELLED", "CANCELED"):
            continue
        pay_total += float(item.get("nao_pago", item.get("total", 0)) or 0)

    return NetPosition(
        receivable_total=recv_total,
        payable_total=pay_total,
        net_position=recv_total - pay_total,
    )


# ─── Liquidez (legado, mantido para compatibilidade) ───

def calculate_liquidity(
    cash_total: float,
    receivables_aging_amounts: dict[str, float],
    payables_aging_amounts: dict[str, float],
) -> dict:
    """Calcula indicadores de liquidez."""
    total_recv = sum(receivables_aging_amounts.values())
    total_pay = sum(payables_aging_amounts.values())
    current_assets = cash_total + total_recv

    rec_30d = receivables_aging_amounts.get("0-30d", 0)
    pay_short = (
        payables_aging_amounts.get("Vencido", 0)
        + payables_aging_amounts.get("0-30d", 0)
    )

    return {
        "quick_ratio": (cash_total + rec_30d) / pay_short if pay_short > 0 else 0,
        "current_ratio": current_assets / total_pay if total_pay > 0 else 0,
        "working_capital": current_assets - total_pay,
    }
