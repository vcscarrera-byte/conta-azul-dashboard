"""
Modelos de dados financeiros.
Dataclasses tipadas para resultados de cálculos do dashboard.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd


# ─── Cash Flow Projection ───

@dataclass
class CashProjection:
    """Resultado da projeção de fluxo de caixa."""
    daily: pd.DataFrame  # columns: date, balance
    min_balance: float = 0.0
    min_balance_date: Optional[date] = None
    days_until_negative: Optional[int] = None
    balance_30d: float = 0.0
    balance_60d: float = 0.0


# ─── Burn Rate ───

@dataclass
class BurnRate:
    """Taxa de queima mensal."""
    monthly_average: float = 0.0
    months_used: int = 0
    monthly_breakdown: list = field(default_factory=list)


# ─── Runway ───

@dataclass
class Runway:
    """Tempo restante de operação."""
    months: float = 0.0
    is_infinite: bool = False


# ─── Delinquency ───

@dataclass
class Delinquency:
    """Indicadores de inadimplência."""
    total_receivable: float = 0.0
    overdue_receivable: float = 0.0
    delinquency_rate: float = 0.0
    overdue_count: int = 0
    total_count: int = 0


# ─── Net Position ───

@dataclass
class NetPosition:
    """Posição líquida."""
    receivable_total: float = 0.0
    payable_total: float = 0.0
    net_position: float = 0.0


# ─── Cash History ───

@dataclass
class CashHistory:
    """Histórico mensal de caixa estimado."""
    monthly: pd.DataFrame  # columns: month, balance


# ─── Aging ───

@dataclass
class AgingBucket:
    """Um bucket de aging."""
    label: str
    amount: float = 0.0
    count: int = 0


@dataclass
class AgingSummary:
    """Resumo de aging (receber ou pagar)."""
    buckets: list[AgingBucket] = field(default_factory=list)
    total: float = 0.0


# ─── Revenue vs Expenses ───

@dataclass
class MonthlyResult:
    """Linha de receita vs despesa mensal."""
    month_label: str
    month_key: str
    revenue: float = 0.0
    expense: float = 0.0
    result: float = 0.0


# ─── Expense Breakdown ───

@dataclass
class CategoryExpense:
    """Despesa por categoria."""
    name: str
    amount: float = 0.0
    percentage: float = 0.0
