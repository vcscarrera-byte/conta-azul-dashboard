"""
Serviço de Fluxo de Caixa.

Responsabilidades:
- Projeção de caixa (cash projection)
- Histórico de caixa estimado
- Aging de recebíveis e pagáveis
"""

from datetime import date, timedelta
from typing import Optional

import pandas as pd

from dashboard.models.financial_models import (
    CashProjection,
    CashHistory,
    AgingBucket,
    AgingSummary,
    MonthlyResult,
    CategoryExpense,
)
from dashboard.config import PROJECTION_DAYS, LOOKBACK_DAYS


# ─── Classificação de aging ───

BUCKET_ORDER = ["Vencido", "0-30d", "31-60d", "60+d"]


def _classify_aging_bucket(due_date_str: Optional[str], ref_date: date = None) -> str:
    ref = ref_date or date.today()
    if not due_date_str:
        return "Vencido"
    try:
        dt = date.fromisoformat(due_date_str[:10])
    except (ValueError, TypeError):
        return "Vencido"
    diff = (dt - ref).days
    if diff < 0:
        return "Vencido"
    if diff <= 30:
        return "0-30d"
    if diff <= 60:
        return "31-60d"
    return "60+d"


def _is_open(item: dict) -> bool:
    """Verifica se um título está em aberto (não pago/cancelado)."""
    status = (item.get("status") or "").upper()
    return status not in ("PAID", "CANCELLED", "CANCELED")


def _unpaid_amount(item: dict) -> float:
    """Retorna o valor não pago de um título."""
    return float(item.get("nao_pago", item.get("total", 0)) or 0)


def _paid_amount(item: dict) -> float:
    """Retorna o valor pago de um título."""
    return float(item.get("pago", 0) or 0)


# ─── Cash Projection ───

def build_cash_projection(
    current_cash: float,
    receivables: list[dict],
    payables: list[dict],
    days: int = PROJECTION_DAYS,
) -> CashProjection:
    """
    Projeta o saldo de caixa dia a dia.

    Algoritmo:
    1. Inicia com current_cash
    2. Para cada dia futuro:
       - Soma recebíveis com vencimento no dia
       - Subtrai pagáveis com vencimento no dia
    """
    today = date.today()

    # Mapa de fluxos por data
    daily_inflows: dict[date, float] = {}
    daily_outflows: dict[date, float] = {}

    for item in receivables:
        if not _is_open(item):
            continue
        amount = _unpaid_amount(item)
        if amount <= 0:
            continue
        due_str = item.get("data_vencimento")
        if not due_str:
            continue
        try:
            due_date = date.fromisoformat(due_str[:10])
        except (ValueError, TypeError):
            continue
        if due_date < today:
            # Vencidos: assume recebimento hoje
            daily_inflows[today] = daily_inflows.get(today, 0) + amount
        else:
            daily_inflows[due_date] = daily_inflows.get(due_date, 0) + amount

    for item in payables:
        if not _is_open(item):
            continue
        amount = _unpaid_amount(item)
        if amount <= 0:
            continue
        due_str = item.get("data_vencimento")
        if not due_str:
            continue
        try:
            due_date = date.fromisoformat(due_str[:10])
        except (ValueError, TypeError):
            continue
        if due_date < today:
            # Vencidos: assume pagamento hoje
            daily_outflows[today] = daily_outflows.get(today, 0) + amount
        else:
            daily_outflows[due_date] = daily_outflows.get(due_date, 0) + amount

    # Projetar dia a dia
    rows = []
    balance = current_cash
    min_balance = balance
    min_balance_date = today
    days_until_negative = None
    balance_30d = balance
    balance_60d = balance

    for i in range(days + 1):
        d = today + timedelta(days=i)
        balance += daily_inflows.get(d, 0)
        balance -= daily_outflows.get(d, 0)

        rows.append({"date": d, "balance": balance})

        if balance < min_balance:
            min_balance = balance
            min_balance_date = d

        if balance < 0 and days_until_negative is None:
            days_until_negative = i

        if i == 30:
            balance_30d = balance
        if i == 60:
            balance_60d = balance

    df = pd.DataFrame(rows)

    return CashProjection(
        daily=df,
        min_balance=min_balance,
        min_balance_date=min_balance_date,
        days_until_negative=days_until_negative,
        balance_30d=balance_30d,
        balance_60d=balance_60d,
    )


# ─── Aging ───

def compute_aging(items: list[dict], filter_open: bool = True) -> AgingSummary:
    """Agrupa títulos por bucket de aging."""
    buckets = {b: AgingBucket(label=b) for b in BUCKET_ORDER}

    for item in items:
        if filter_open and not _is_open(item):
            continue
        amount = _unpaid_amount(item)
        if amount <= 0:
            continue

        bucket_key = _classify_aging_bucket(item.get("data_vencimento"))
        if bucket_key in buckets:
            buckets[bucket_key].amount += amount
            buckets[bucket_key].count += 1

    bucket_list = [buckets[b] for b in BUCKET_ORDER]
    total = sum(b.amount for b in bucket_list)

    return AgingSummary(buckets=bucket_list, total=total)


# ─── Revenue vs Expense mensal ───

MONTH_NAMES_PT = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}


def compute_monthly_revenue_expenses(
    receivables: list[dict],
    payables: list[dict],
    months: int = 6,
) -> list[MonthlyResult]:
    """Agrega receita (pago) e despesa (pago) por mês."""
    today = date.today()
    start = (today.replace(day=1) - timedelta(days=months * 30)).replace(day=1)

    # Gerar labels de meses
    month_keys = []
    current = start
    while current <= today:
        month_keys.append(current.strftime("%Y-%m"))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    revenue = {m: 0.0 for m in month_keys}
    expense = {m: 0.0 for m in month_keys}

    for item in receivables:
        pago = _paid_amount(item)
        if pago <= 0:
            continue
        dt_str = item.get("data_competencia", item.get("data_vencimento", ""))
        if dt_str:
            mk = dt_str[:7]
            if mk in revenue:
                revenue[mk] += pago

    for item in payables:
        pago = _paid_amount(item)
        if pago <= 0:
            continue
        dt_str = item.get("data_competencia", item.get("data_vencimento", ""))
        if dt_str:
            mk = dt_str[:7]
            if mk in expense:
                expense[mk] += pago

    results = []
    for mk in month_keys:
        mm = mk.split("-")[1]
        label = f"{MONTH_NAMES_PT.get(mm, mm)}/{mk[:4]}"
        r = revenue[mk]
        d = expense[mk]
        results.append(MonthlyResult(
            month_label=label,
            month_key=mk,
            revenue=r,
            expense=d,
            result=r - d,
        ))

    return results


# ─── Expense Breakdown ───

def compute_expense_breakdown(payables: list[dict], top_n: int = 8) -> list[CategoryExpense]:
    """Despesas por categoria do mês corrente."""
    today = date.today()
    current_month = today.strftime("%Y-%m")

    cat_totals: dict[str, float] = {}

    for item in payables:
        valor = float(item.get("total", 0) or 0)
        if valor <= 0:
            continue

        # Filtrar só mês atual pela data de vencimento
        dt_str = item.get("data_vencimento", "")
        if not dt_str or dt_str[:7] != current_month:
            continue

        cats = item.get("categorias", [])
        cat_name = cats[0].get("nome", "Sem categoria") if cats else "Sem categoria"
        cat_totals[cat_name] = cat_totals.get(cat_name, 0) + valor

    if not cat_totals:
        return []

    sorted_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
    top = sorted_cats[:top_n]
    others_sum = sum(v for _, v in sorted_cats[top_n:])

    total = sum(v for _, v in sorted_cats)
    results = []

    for name, val in top:
        results.append(CategoryExpense(
            name=name,
            amount=val,
            percentage=(val / total * 100) if total > 0 else 0,
        ))

    if others_sum > 0:
        results.append(CategoryExpense(
            name="Outros",
            amount=others_sum,
            percentage=(others_sum / total * 100) if total > 0 else 0,
        ))

    return results


# ─── Cash History (estimado) ───

def build_cash_history(
    receivables: list[dict],
    payables: list[dict],
    current_cash: float,
    months: int = 12,
) -> CashHistory:
    """
    Estima histórico mensal de saldo de caixa.

    Método: trabalha de trás para frente a partir do caixa atual,
    revertendo fluxos pagos mês a mês.
    """
    today = date.today()

    # Agregar fluxos pagos por mês
    monthly_inflows: dict[str, float] = {}
    monthly_outflows: dict[str, float] = {}

    for item in receivables:
        pago = _paid_amount(item)
        if pago <= 0:
            continue
        dt_str = item.get("data_competencia", item.get("data_vencimento", ""))
        if dt_str:
            mk = dt_str[:7]
            monthly_inflows[mk] = monthly_inflows.get(mk, 0) + pago

    for item in payables:
        pago = _paid_amount(item)
        if pago <= 0:
            continue
        dt_str = item.get("data_competencia", item.get("data_vencimento", ""))
        if dt_str:
            mk = dt_str[:7]
            monthly_outflows[mk] = monthly_outflows.get(mk, 0) + pago

    # Gerar meses (do mais recente ao mais antigo)
    month_keys = []
    current = today.replace(day=1)
    for _ in range(months):
        month_keys.append(current.strftime("%Y-%m"))
        current = (current - timedelta(days=1)).replace(day=1)

    month_keys.reverse()  # mais antigo primeiro

    # Calcular de trás para frente
    rows = []
    balance = current_cash
    current_month = today.strftime("%Y-%m")

    # Do mês atual para trás: reverter fluxos
    reversed_keys = list(reversed(month_keys))
    balances = {}

    for i, mk in enumerate(reversed_keys):
        if i == 0:
            balances[mk] = balance
        else:
            # Reverter: subtrair inflows e somar outflows do mês seguinte
            prev_mk = reversed_keys[i - 1]
            inflow = monthly_inflows.get(prev_mk, 0)
            outflow = monthly_outflows.get(prev_mk, 0)
            balance = balance - inflow + outflow
            balances[mk] = balance

    for mk in month_keys:
        mm = mk.split("-")[1]
        label = f"{MONTH_NAMES_PT.get(mm, mm)}/{mk[:4]}"
        rows.append({"month": label, "month_key": mk, "balance": balances.get(mk, 0)})

    return CashHistory(monthly=pd.DataFrame(rows))
