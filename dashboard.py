"""
Dashboard CFO - Conta Azul
Painel mínimo para acompanhar a saúde financeira da empresa.

Executar: streamlit run dashboard.py --server.port 8502
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from dashboard_data import DashboardData, format_brl

# ─── Configuração da Página ───

st.set_page_config(
    page_title="Dashboard CFO",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# CSS customizado para KPIs e layout
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
        font-size: 1.5rem !important;
    }
    .block-container {
        padding-top: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)


# ─── Cache de Dados ───

@st.cache_data(ttl=300, show_spinner=False)
def load_all_data():
    """Carrega todos os dados do dashboard (cache de 5 min)."""
    data = DashboardData()
    return {
        "cash": data.get_cash_position(),
        "ratios": data.get_liquidity_ratios(),
        "receivables": data.get_receivables_aging(),
        "payables": data.get_payables_aging(),
        "monthly": data.get_monthly_revenue_expenses(),
        "expenses": data.get_expense_breakdown(),
    }


# ─── Sidebar ───

with st.sidebar:
    st.title("⚙️ Configurações")
    if st.button("🔄 Atualizar Dados", use_container_width=True):
        load_all_data.clear()
        st.rerun()
    st.caption("Dados atualizados a cada 5 minutos.")


# ─── Cabeçalho ───

st.title("📊 Dashboard CFO")
st.caption("Visão financeira consolidada · Conta Azul")

st.divider()

# ─── Carregar Dados ───

try:
    with st.spinner("Carregando dados da Conta Azul..."):
        dados = load_all_data()
except Exception as e:
    st.error(f"Erro ao conectar com a API da Conta Azul: {e}")
    st.info("Verifique se o token está válido (execute `python exemplo.py` para renovar).")
    st.stop()


# ═══════════════════════════════════════════════════════
# ROW 1 — KPIs
# ═══════════════════════════════════════════════════════

ratios = dados["ratios"]
cash = dados["cash"]

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="💰 Posição de Caixa",
        value=format_brl(ratios["total_cash"]),
    )

with col2:
    qi = ratios["quick_ratio"]
    st.metric(
        label="⚡ Liquidez Imediata",
        value=f"{qi:.2f}x" if qi > 0 else "N/A",
        help="(Caixa + Recebíveis 0-30d) / Passivo curto prazo",
    )

with col3:
    wc = ratios["working_capital"]
    st.metric(
        label="🔄 Capital de Giro",
        value=format_brl(wc),
        help="Ativo corrente − Passivo corrente",
    )

with col4:
    cr = ratios["current_ratio"]
    st.metric(
        label="📈 Liquidez Corrente",
        value=f"{cr:.2f}x" if cr > 0 else "N/A",
        help="Ativo corrente / Passivo corrente",
    )

# Detalhamento de contas (expander)
if cash["contas"]:
    with st.expander("Detalhamento por conta bancária"):
        for conta in cash["contas"]:
            st.write(f"**{conta['nome']}**: {format_brl(conta['saldo'])}")

st.divider()

# ═══════════════════════════════════════════════════════
# ROW 2 — Aging (Receber e Pagar)
# ═══════════════════════════════════════════════════════

col_rec, col_pay = st.columns(2)

# Cores dos buckets
AGING_COLORS = {
    "Vencido": "#dc3545",
    "0-30d": "#ffc107",
    "31-60d": "#17a2b8",
    "60+d": "#6c757d",
}


def make_aging_chart(df, title):
    """Cria gráfico de barras horizontais para aging."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=df["bucket"],
        x=df["valor_total"],
        orientation="h",
        marker_color=[AGING_COLORS.get(b, "#999") for b in df["bucket"]],
        text=[
            f"{format_brl(v)}  ({q} {'título' if q == 1 else 'títulos'})"
            for v, q in zip(df["valor_total"], df["quantidade"])
        ],
        textposition="auto",
        textfont=dict(size=12),
    ))

    total = df["valor_total"].sum()
    fig.update_layout(
        title=dict(text=f"{title}<br><sup>{format_brl(total)} total</sup>", font_size=16),
        height=280,
        margin=dict(l=10, r=10, t=60, b=10),
        xaxis=dict(visible=False),
        yaxis=dict(autorange="reversed"),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
    )

    return fig


with col_rec:
    try:
        rec_df = dados["receivables"]
        fig_rec = make_aging_chart(rec_df, "📥 Contas a Receber")
        st.plotly_chart(fig_rec, use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao renderizar Contas a Receber: {e}")

with col_pay:
    try:
        pay_df = dados["payables"]
        fig_pay = make_aging_chart(pay_df, "📤 Contas a Pagar")
        st.plotly_chart(fig_pay, use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao renderizar Contas a Pagar: {e}")

st.divider()

# ═══════════════════════════════════════════════════════
# ROW 3 — Receita vs Despesa + Despesas por Categoria
# ═══════════════════════════════════════════════════════

col_monthly, col_donut = st.columns(2)

with col_monthly:
    try:
        monthly_df = dados["monthly"]

        fig_monthly = go.Figure()

        # Barras de receita
        fig_monthly.add_trace(go.Bar(
            x=monthly_df["mes"],
            y=monthly_df["receita"],
            name="Receita",
            marker_color="#28a745",
            text=[format_brl(v) for v in monthly_df["receita"]],
            textposition="outside",
            textfont=dict(size=10),
        ))

        # Barras de despesa
        fig_monthly.add_trace(go.Bar(
            x=monthly_df["mes"],
            y=monthly_df["despesa"],
            name="Despesa",
            marker_color="#dc3545",
            text=[format_brl(v) for v in monthly_df["despesa"]],
            textposition="outside",
            textfont=dict(size=10),
        ))

        # Linha de resultado
        fig_monthly.add_trace(go.Scatter(
            x=monthly_df["mes"],
            y=monthly_df["resultado"],
            name="Resultado",
            mode="lines+markers+text",
            line=dict(color="#007bff", width=2),
            marker=dict(size=8),
            text=[format_brl(v) for v in monthly_df["resultado"]],
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
    except Exception as e:
        st.error(f"Erro ao renderizar Receita vs Despesa: {e}")

with col_donut:
    try:
        exp_df = dados["expenses"]

        if exp_df["valor"].sum() > 0:
            fig_donut = go.Figure(go.Pie(
                labels=exp_df["categoria"],
                values=exp_df["valor"],
                hole=0.5,
                textinfo="label+percent",
                textposition="outside",
                textfont=dict(size=11),
                marker=dict(colors=px.colors.qualitative.Set2),
            ))

            total_exp = exp_df["valor"].sum()
            fig_donut.update_layout(
                title=dict(text="🏷️ Despesas por Categoria (Mês Atual)", font_size=16),
                height=380,
                margin=dict(l=10, r=10, t=50, b=10),
                showlegend=False,
                annotations=[dict(
                    text=f"{format_brl(total_exp)}",
                    x=0.5, y=0.5, font_size=14, showarrow=False,
                )],
            )

            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("Nenhuma despesa registrada no mês atual.")
    except Exception as e:
        st.error(f"Erro ao renderizar Despesas por Categoria: {e}")


# ─── Rodapé ───

st.divider()
st.caption("Dashboard CFO · Dados via API Conta Azul · Atualização automática a cada 5 min")
