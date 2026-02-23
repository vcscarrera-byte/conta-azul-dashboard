"""
Dashboard CFO — Conta Azul
Painel executivo de saúde financeira.

Executar:
    streamlit run dashboard/app.py --server.port 8502
"""

import sys
from pathlib import Path

# Garante que o diretório raiz do projeto está no sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from dashboard.api.contaazul_client import ContaAzulClient
from dashboard.services.cashflow_service import (
    build_cash_projection,
    compute_aging,
    compute_monthly_revenue_expenses,
    compute_expense_breakdown,
    build_cash_history,
)
from dashboard.services.metrics_service import (
    calculate_burn_rate,
    calculate_runway,
    calculate_delinquency,
    calculate_net_position,
    calculate_liquidity,
)
from dashboard.utils.formatting import format_brl, format_percent, format_months
from dashboard.config import (
    CACHE_TTL,
    PROJECTION_DAYS,
    DELINQUENCY_WARNING_THRESHOLD,
)


# ═══════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════

st.set_page_config(
    page_title="Dashboard CFO",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 16px;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
        color: #6c757d !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
    .block-container {
        padding-top: 1.5rem;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════
# DATA LOADING (cached)
# ═══════════════════════════════════════════════════════

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_raw_data():
    """Busca todos os dados brutos da API (cache de 5 min)."""
    client = ContaAzulClient()
    cash = client.get_cash_balance()
    receivables = client.get_receivables()
    payables = client.get_payables()
    return cash, receivables, payables


def compute_all_metrics(cash: dict, receivables: list, payables: list) -> dict:
    """Computa todas as métricas a partir dos dados brutos."""
    current_cash = cash["total"]

    # Aging
    recv_aging = compute_aging(receivables)
    pay_aging = compute_aging(payables)

    recv_aging_map = {b.label: b.amount for b in recv_aging.buckets}
    pay_aging_map = {b.label: b.amount for b in pay_aging.buckets}

    # Projeção de caixa
    projection = build_cash_projection(
        current_cash=current_cash,
        receivables=receivables,
        payables=payables,
        days=PROJECTION_DAYS,
    )

    # Burn Rate & Runway
    burn = calculate_burn_rate(payables)
    runway = calculate_runway(current_cash, burn.monthly_average)

    # Inadimplência
    delinquency = calculate_delinquency(receivables)

    # Posição Líquida
    net_pos = calculate_net_position(receivables, payables)

    # Liquidez
    liquidity = calculate_liquidity(current_cash, recv_aging_map, pay_aging_map)

    # Receita vs Despesa
    monthly = compute_monthly_revenue_expenses(receivables, payables)

    # Despesas por categoria
    expenses = compute_expense_breakdown(payables)

    # Histórico de caixa
    cash_history = build_cash_history(receivables, payables, current_cash)

    return {
        "cash": cash,
        "current_cash": current_cash,
        "projection": projection,
        "burn": burn,
        "runway": runway,
        "delinquency": delinquency,
        "net_pos": net_pos,
        "liquidity": liquidity,
        "recv_aging": recv_aging,
        "pay_aging": pay_aging,
        "monthly": monthly,
        "expenses": expenses,
        "cash_history": cash_history,
    }


# ═══════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════

with st.sidebar:
    st.title("⚙️ Configurações")
    if st.button("🔄 Atualizar Dados", use_container_width=True):
        load_raw_data.clear()
        st.rerun()
    st.caption("Cache: 5 minutos")
    st.divider()
    st.caption("Dashboard CFO v2.0")


# ═══════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════

st.title("📊 Dashboard CFO")
st.caption("Visão financeira consolidada · Conta Azul")

# ═══════════════════════════════════════════════════════
# LOAD & COMPUTE
# ═══════════════════════════════════════════════════════

try:
    with st.spinner("Carregando dados da Conta Azul..."):
        cash_raw, recv_raw, pay_raw = load_raw_data()
        m = compute_all_metrics(cash_raw, recv_raw, pay_raw)
except Exception as e:
    st.error(f"Erro ao conectar com a API: {e}")
    st.info("Verifique se o token está válido. Execute:\n`python -m dashboard.api.auth`")
    st.stop()


# ═══════════════════════════════════════════════════════
# WARNINGS
# ═══════════════════════════════════════════════════════

warnings = []

proj = m["projection"]
if proj.days_until_negative is not None:
    warnings.append(
        f"⚠️ **Déficit de caixa previsto em {proj.days_until_negative} dias** "
        f"(saldo mínimo projetado: {format_brl(proj.min_balance)} em {proj.min_balance_date})"
    )

delinq = m["delinquency"]
if delinq.delinquency_rate > DELINQUENCY_WARNING_THRESHOLD * 100:
    warnings.append(
        f"⚠️ **Inadimplência alta: {format_percent(delinq.delinquency_rate)}** "
        f"({delinq.overdue_count} títulos vencidos = {format_brl(delinq.overdue_receivable)})"
    )

burn = m["burn"]
runway = m["runway"]
if not runway.is_infinite and runway.months < 6:
    warnings.append(
        f"⚠️ **Runway curto: {runway.months:.1f} meses** "
        f"(burn rate mensal: {format_brl(burn.monthly_average)})"
    )

if warnings:
    for w in warnings:
        st.warning(w)
    st.divider()


# ═══════════════════════════════════════════════════════
# ROW 1 — KPIs ESTRATÉGICOS (4 cards)
# ═══════════════════════════════════════════════════════

st.subheader("Indicadores Estratégicos")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        label="💰 Caixa Hoje",
        value=format_brl(m["current_cash"]),
    )

with c2:
    st.metric(
        label="📅 Caixa em 30 Dias",
        value=format_brl(proj.balance_30d),
        delta=format_brl(proj.balance_30d - m["current_cash"]),
        help="Projeção baseada em recebíveis e pagáveis com vencimento nos próximos 30 dias",
    )

with c3:
    st.metric(
        label="🔥 Burn Rate Mensal",
        value=format_brl(burn.monthly_average),
        help=f"Média dos últimos {burn.months_used} meses com despesas",
    )

with c4:
    rw_display = format_months(runway.months) if not runway.is_infinite else "∞"
    st.metric(
        label="⏳ Runway",
        value=rw_display,
        help="Meses de operação restantes = Caixa / Burn Rate",
    )


# ═══════════════════════════════════════════════════════
# ROW 2 — KPIs OPERACIONAIS (4 cards)
# ═══════════════════════════════════════════════════════

st.divider()

c5, c6, c7, c8 = st.columns(4)

net = m["net_pos"]
liq = m["liquidity"]

with c5:
    st.metric(
        label="📥 A Receber",
        value=format_brl(net.receivable_total),
        help=f"{m['recv_aging'].total:.0f} em aberto",
    )

with c6:
    st.metric(
        label="📤 A Pagar",
        value=format_brl(net.payable_total),
    )

with c7:
    delta_color = "normal" if net.net_position >= 0 else "inverse"
    st.metric(
        label="📊 Posição Líquida",
        value=format_brl(net.net_position),
        delta_color=delta_color,
        help="Recebíveis pendentes − Pagáveis pendentes",
    )

with c8:
    st.metric(
        label="🚨 Inadimplência",
        value=format_percent(delinq.delinquency_rate),
        help=(
            f"{delinq.overdue_count} de {delinq.total_count} títulos vencidos\n"
            f"= {format_brl(delinq.overdue_receivable)} de {format_brl(delinq.total_receivable)}"
        ),
    )

# Detalhamento por conta (expander)
if m["cash"]["contas"]:
    with st.expander("Detalhamento por conta bancária"):
        contas_df = pd.DataFrame(m["cash"]["contas"])
        contas_df = contas_df[contas_df["saldo"] != 0].sort_values("saldo", ascending=False)
        for _, row in contas_df.iterrows():
            st.write(f"**{row['nome']}** ({row['tipo']}): {format_brl(row['saldo'])}")


# ═══════════════════════════════════════════════════════
# ROW 3 — PROJEÇÃO DE CAIXA (full width)
# ═══════════════════════════════════════════════════════

st.divider()
st.subheader("Projeção de Caixa")

df_proj = proj.daily.copy()

fig_proj = go.Figure()

# Área de projeção
fig_proj.add_trace(go.Scatter(
    x=df_proj["date"],
    y=df_proj["balance"],
    mode="lines",
    fill="tozeroy",
    line=dict(color="#007bff", width=2),
    fillcolor="rgba(0,123,255,0.1)",
    name="Saldo Projetado",
    hovertemplate="<b>%{x}</b><br>Saldo: R$ %{y:,.2f}<extra></extra>",
))

# Linha de zero (referência)
fig_proj.add_hline(y=0, line_dash="dash", line_color="red", opacity=0.5)

# Marcadores de 30d e 60d
from datetime import date as dt_date, timedelta
today = dt_date.today()

for offset, label in [(30, "30d"), (60, "60d")]:
    mark_date = today + timedelta(days=offset)
    fig_proj.add_shape(
        type="line",
        x0=mark_date, x1=mark_date,
        y0=0, y1=1,
        yref="paper",
        line=dict(color="#6c757d", dash="dot", width=1),
        opacity=0.5,
    )
    fig_proj.add_annotation(
        x=mark_date, y=1, yref="paper",
        text=label, showarrow=False,
        font=dict(size=10, color="#6c757d"),
        yshift=10,
    )

# Marcador de saldo mínimo
if proj.min_balance_date:
    fig_proj.add_trace(go.Scatter(
        x=[proj.min_balance_date],
        y=[proj.min_balance],
        mode="markers+text",
        marker=dict(color="red", size=10, symbol="diamond"),
        text=[f"Mín: {format_brl(proj.min_balance)}"],
        textposition="bottom center",
        textfont=dict(size=10, color="red"),
        name="Saldo Mínimo",
        showlegend=False,
    ))

fig_proj.update_layout(
    height=350,
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(title=""),
    yaxis=dict(title="R$", tickformat=",.0f"),
    showlegend=False,
    plot_bgcolor="rgba(0,0,0,0)",
    hovermode="x unified",
)

st.plotly_chart(fig_proj, use_container_width=True)

# Sub-métricas da projeção
pc1, pc2, pc3 = st.columns(3)
with pc1:
    st.caption(f"Caixa em 30d: **{format_brl(proj.balance_30d)}**")
with pc2:
    st.caption(f"Caixa em 60d: **{format_brl(proj.balance_60d)}**")
with pc3:
    if proj.days_until_negative is not None:
        st.caption(f"🔴 Déficit em: **{proj.days_until_negative} dias**")
    else:
        st.caption("🟢 Caixa positivo nos próximos 60 dias")


# ═══════════════════════════════════════════════════════
# ROW 4 — AGING (Receber + Pagar)
# ═══════════════════════════════════════════════════════

st.divider()

AGING_COLORS = {
    "Vencido": "#dc3545",
    "0-30d": "#ffc107",
    "31-60d": "#17a2b8",
    "60+d": "#6c757d",
}


def make_aging_chart(aging_summary, title: str):
    fig = go.Figure()
    labels = [b.label for b in aging_summary.buckets]
    values = [b.amount for b in aging_summary.buckets]
    counts = [b.count for b in aging_summary.buckets]
    colors = [AGING_COLORS.get(b.label, "#999") for b in aging_summary.buckets]

    fig.add_trace(go.Bar(
        y=labels,
        x=values,
        orientation="h",
        marker_color=colors,
        text=[
            f"{format_brl(v)}  ({c} {'título' if c == 1 else 'títulos'})"
            for v, c in zip(values, counts)
        ],
        textposition="auto",
        textfont=dict(size=12),
    ))

    fig.update_layout(
        title=dict(
            text=f"{title}<br><sup>{format_brl(aging_summary.total)} total</sup>",
            font_size=16,
        ),
        height=280,
        margin=dict(l=10, r=10, t=60, b=10),
        xaxis=dict(visible=False),
        yaxis=dict(autorange="reversed"),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


col_recv, col_pay = st.columns(2)

with col_recv:
    fig_recv = make_aging_chart(m["recv_aging"], "📥 Contas a Receber")
    st.plotly_chart(fig_recv, use_container_width=True)

with col_pay:
    fig_pay = make_aging_chart(m["pay_aging"], "📤 Contas a Pagar")
    st.plotly_chart(fig_pay, use_container_width=True)


# ═══════════════════════════════════════════════════════
# ROW 5 — RECEITA VS DESPESA
# ═══════════════════════════════════════════════════════

st.divider()

monthly_data = m["monthly"]

fig_monthly = go.Figure()

fig_monthly.add_trace(go.Bar(
    x=[r.month_label for r in monthly_data],
    y=[r.revenue for r in monthly_data],
    name="Receita",
    marker_color="#28a745",
    text=[format_brl(r.revenue) for r in monthly_data],
    textposition="outside",
    textfont=dict(size=10),
))

fig_monthly.add_trace(go.Bar(
    x=[r.month_label for r in monthly_data],
    y=[r.expense for r in monthly_data],
    name="Despesa",
    marker_color="#dc3545",
    text=[format_brl(r.expense) for r in monthly_data],
    textposition="outside",
    textfont=dict(size=10),
))

fig_monthly.add_trace(go.Scatter(
    x=[r.month_label for r in monthly_data],
    y=[r.result for r in monthly_data],
    name="Resultado",
    mode="lines+markers+text",
    line=dict(color="#007bff", width=2),
    marker=dict(size=8),
    text=[format_brl(r.result) for r in monthly_data],
    textposition="top center",
    textfont=dict(size=9, color="#007bff"),
))

fig_monthly.update_layout(
    title=dict(text="📊 Receita vs Despesa (Mensal)", font_size=16),
    barmode="group",
    height=380,
    margin=dict(l=10, r=10, t=50, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title="R$", tickformat=",.0f"),
    plot_bgcolor="rgba(0,0,0,0)",
)

st.plotly_chart(fig_monthly, use_container_width=True)


# ═══════════════════════════════════════════════════════
# ROW 6 — DESPESAS POR CATEGORIA
# ═══════════════════════════════════════════════════════

st.divider()

expenses = m["expenses"]

if expenses:
    fig_donut = go.Figure(go.Pie(
        labels=[e.name for e in expenses],
        values=[e.amount for e in expenses],
        hole=0.5,
        textinfo="label+percent",
        textposition="outside",
        textfont=dict(size=11),
        marker=dict(colors=px.colors.qualitative.Set2),
    ))

    total_exp = sum(e.amount for e in expenses)
    fig_donut.update_layout(
        title=dict(text="🏷️ Despesas por Categoria (Mês Atual)", font_size=16),
        height=380,
        margin=dict(l=10, r=10, t=50, b=10),
        showlegend=False,
        annotations=[dict(
            text=format_brl(total_exp),
            x=0.5, y=0.5, font_size=14, showarrow=False,
        )],
    )

    st.plotly_chart(fig_donut, use_container_width=True)
else:
    st.info("Nenhuma despesa registrada no mês atual.")


# ═══════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════

st.divider()
st.caption("Dashboard CFO v2.0 · Dados via API Conta Azul · Atualização automática a cada 5 min")
