"""
Dashboard CFO — Conta Azul + Banco Inter PJ
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
from dashboard.services.reconciliation_service import reconcile
from dashboard.config import (
    CACHE_TTL,
    PROJECTION_DAYS,
    DELINQUENCY_WARNING_THRESHOLD,
    INTER_ENABLED,
)
from dashboard.styles import CUSTOM_CSS, PLOTLY_TEMPLATE, COLORS, CHART_COLORS, AGING_COLORS
from dashboard.components import (
    dashboard_header,
    section_header,
    warning_banner,
    footer,
)


# ═══════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════

st.set_page_config(
    page_title="Dashboard CFO",
    page_icon="https://em-content.zobj.net/source/apple/391/chart-increasing_1f4c8.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


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


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_inter_data():
    """Busca saldo e extrato do Banco Inter PJ (cache de 5 min)."""
    from dashboard.api.inter_client import InterClient
    client = InterClient()
    balance = client.get_balance()
    statement = client.get_statement()
    return balance, statement


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
    st.title("Configuracoes")
    if st.button("Atualizar Dados", use_container_width=True):
        load_raw_data.clear()
        if INTER_ENABLED:
            load_inter_data.clear()
        st.rerun()
    st.caption("Cache: 5 minutos")
    st.divider()
    if INTER_ENABLED:
        st.success("Banco Inter: Conectado")
    else:
        st.info("Banco Inter: Nao configurado")
    st.divider()
    st.caption("Dashboard CFO v3.0")


# ═══════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════

sources = "Conta Azul"
if INTER_ENABLED:
    sources += " + Banco Inter"

st.markdown(dashboard_header(version="v3.0", sources=sources), unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════
# LOAD & COMPUTE
# ═══════════════════════════════════════════════════════

try:
    with st.spinner("Carregando dados da Conta Azul..."):
        cash_raw, recv_raw, pay_raw = load_raw_data()
        m = compute_all_metrics(cash_raw, recv_raw, pay_raw)
except Exception as e:
    st.error(f"Erro ao conectar com a API: {e}")
    st.info("Verifique se o token esta valido. Execute:\n`python -m dashboard.api.auth`")
    st.stop()


# ═══════════════════════════════════════════════════════
# WARNINGS
# ═══════════════════════════════════════════════════════

proj = m["projection"]
burn = m["burn"]
runway = m["runway"]
delinq = m["delinquency"]

warnings_html = []

if proj.days_until_negative is not None:
    warnings_html.append(warning_banner(
        f"Deficit de caixa previsto em <strong>{proj.days_until_negative} dias</strong> "
        f"(saldo minimo projetado: {format_brl(proj.min_balance)} em {proj.min_balance_date})"
    ))

if delinq.delinquency_rate > DELINQUENCY_WARNING_THRESHOLD * 100:
    warnings_html.append(warning_banner(
        f"Inadimplencia alta: <strong>{format_percent(delinq.delinquency_rate)}</strong> "
        f"({delinq.overdue_count} titulos vencidos = {format_brl(delinq.overdue_receivable)})"
    ))

if not runway.is_infinite and runway.months < 6:
    warnings_html.append(warning_banner(
        f"Runway curto: <strong>{runway.months:.1f} meses</strong> "
        f"(burn rate mensal: {format_brl(burn.monthly_average)})"
    ))

if warnings_html:
    st.markdown("".join(warnings_html), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════
# ROW 1 — KPIs ESTRATEGICOS
# ═══════════════════════════════════════════════════════

st.markdown(section_header("Indicadores Estrategicos"), unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        label="Caixa Hoje",
        value=format_brl(m["current_cash"]),
    )

with c2:
    st.metric(
        label="Caixa em 30 Dias",
        value=format_brl(proj.balance_30d),
        delta=format_brl(proj.balance_30d - m["current_cash"]),
        help="Projecao baseada em recebiveis e pagaveis com vencimento nos proximos 30 dias",
    )

with c3:
    st.metric(
        label="Burn Rate Mensal",
        value=format_brl(burn.monthly_average),
        help=f"Media dos ultimos {burn.months_used} meses com despesas",
    )

with c4:
    rw_display = format_months(runway.months) if not runway.is_infinite else "∞"
    st.metric(
        label="Runway",
        value=rw_display,
        help="Meses de operacao restantes = Caixa / Burn Rate",
    )


# ═══════════════════════════════════════════════════════
# ROW 2 — KPIs OPERACIONAIS
# ═══════════════════════════════════════════════════════

st.markdown(section_header("Indicadores Operacionais"), unsafe_allow_html=True)

c5, c6, c7, c8 = st.columns(4)

net = m["net_pos"]
liq = m["liquidity"]

with c5:
    st.metric(
        label="A Receber",
        value=format_brl(net.receivable_total),
        help=f"{m['recv_aging'].total:.0f} em aberto",
    )

with c6:
    st.metric(
        label="A Pagar",
        value=format_brl(net.payable_total),
    )

with c7:
    delta_color = "normal" if net.net_position >= 0 else "inverse"
    st.metric(
        label="Posicao Liquida",
        value=format_brl(net.net_position),
        delta_color=delta_color,
        help="Recebiveis pendentes - Pagaveis pendentes",
    )

with c8:
    st.metric(
        label="Inadimplencia",
        value=format_percent(delinq.delinquency_rate),
        help=(
            f"{delinq.overdue_count} de {delinq.total_count} titulos vencidos\n"
            f"= {format_brl(delinq.overdue_receivable)} de {format_brl(delinq.total_receivable)}"
        ),
    )

# Detalhamento por conta (expander)
if m["cash"]["contas"]:
    with st.expander("Detalhamento por conta bancaria"):
        contas_df = pd.DataFrame(m["cash"]["contas"])
        contas_df = contas_df[contas_df["saldo"] != 0].sort_values("saldo", ascending=False)
        for _, row in contas_df.iterrows():
            st.write(f"**{row['nome']}** ({row['tipo']}): {format_brl(row['saldo'])}")


# ═══════════════════════════════════════════════════════
# ROW 3 — PROJECAO DE CAIXA
# ═══════════════════════════════════════════════════════

st.markdown(
    section_header("Projecao de Caixa", f"Proximos {PROJECTION_DAYS} dias"),
    unsafe_allow_html=True,
)

df_proj = proj.daily.copy()

fig_proj = go.Figure()

fig_proj.add_trace(go.Scatter(
    x=df_proj["date"],
    y=df_proj["balance"],
    mode="lines",
    fill="tozeroy",
    line=dict(color=COLORS["primary"], width=2),
    fillcolor="rgba(99,102,241,0.08)",
    name="Saldo Projetado",
    hovertemplate="<b>%{x}</b><br>Saldo: R$ %{y:,.2f}<extra></extra>",
))

# Linha de zero
fig_proj.add_hline(y=0, line_dash="dash", line_color=COLORS["danger"], opacity=0.4)

# Marcadores 30d e 60d
from datetime import date as dt_date, timedelta
today = dt_date.today()

for offset, label in [(30, "30d"), (60, "60d")]:
    mark_date = today + timedelta(days=offset)
    fig_proj.add_shape(
        type="line",
        x0=mark_date, x1=mark_date,
        y0=0, y1=1,
        yref="paper",
        line=dict(color=COLORS["text_muted"], dash="dot", width=1),
        opacity=0.4,
    )
    fig_proj.add_annotation(
        x=mark_date, y=1, yref="paper",
        text=label, showarrow=False,
        font=dict(size=10, color=COLORS["text_muted"]),
        yshift=10,
    )

# Marcador de saldo minimo
if proj.min_balance_date:
    fig_proj.add_trace(go.Scatter(
        x=[proj.min_balance_date],
        y=[proj.min_balance],
        mode="markers+text",
        marker=dict(color=COLORS["danger"], size=10, symbol="diamond"),
        text=[f"Min: {format_brl(proj.min_balance)}"],
        textposition="bottom center",
        textfont=dict(size=10, color=COLORS["danger"]),
        name="Saldo Minimo",
        showlegend=False,
    ))

fig_proj.update_layout(
    template=PLOTLY_TEMPLATE,
    height=350,
    yaxis=dict(title="R$", tickformat=",.0f"),
    showlegend=False,
    hovermode="x unified",
)

st.plotly_chart(fig_proj, use_container_width=True)

# Sub-metricas da projecao
pc1, pc2, pc3 = st.columns(3)
with pc1:
    st.caption(f"Caixa em 30d: **{format_brl(proj.balance_30d)}**")
with pc2:
    st.caption(f"Caixa em 60d: **{format_brl(proj.balance_60d)}**")
with pc3:
    if proj.days_until_negative is not None:
        st.caption(f"Deficit em: **{proj.days_until_negative} dias**")
    else:
        st.caption("Caixa positivo nos proximos 60 dias")


# ═══════════════════════════════════════════════════════
# ROW 4 — AGING (Receber + Pagar)
# ═══════════════════════════════════════════════════════

st.markdown(section_header("Aging de Recebiveis e Pagaveis"), unsafe_allow_html=True)


def make_aging_chart(aging_summary, title: str):
    fig = go.Figure()
    labels = [b.label for b in aging_summary.buckets]
    values = [b.amount for b in aging_summary.buckets]
    counts = [b.count for b in aging_summary.buckets]
    colors = [AGING_COLORS.get(b.label, COLORS["text_muted"]) for b in aging_summary.buckets]

    fig.add_trace(go.Bar(
        y=labels,
        x=values,
        orientation="h",
        marker_color=colors,
        text=[
            f"{format_brl(v)}  ({c} {'titulo' if c == 1 else 'titulos'})"
            for v, c in zip(values, counts)
        ],
        textposition="auto",
        textfont=dict(size=11, color=COLORS["text_primary"]),
    ))

    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=dict(
            text=f"{title}<br><sup style='color:{COLORS['text_muted']}'>{format_brl(aging_summary.total)} total</sup>",
            font=dict(size=14, color=COLORS["text_primary"]),
        ),
        height=280,
        margin=dict(l=10, r=10, t=60, b=10),
        xaxis=dict(visible=False),
        yaxis=dict(autorange="reversed"),
        showlegend=False,
    )
    return fig


col_recv, col_pay = st.columns(2)

with col_recv:
    fig_recv = make_aging_chart(m["recv_aging"], "Contas a Receber")
    st.plotly_chart(fig_recv, use_container_width=True)

with col_pay:
    fig_pay = make_aging_chart(m["pay_aging"], "Contas a Pagar")
    st.plotly_chart(fig_pay, use_container_width=True)


# ═══════════════════════════════════════════════════════
# ROW 5 — RECEITA VS DESPESA
# ═══════════════════════════════════════════════════════

st.markdown(section_header("Receita vs Despesa", "Visao mensal"), unsafe_allow_html=True)

monthly_data = m["monthly"]

fig_monthly = go.Figure()

fig_monthly.add_trace(go.Bar(
    x=[r.month_label for r in monthly_data],
    y=[r.revenue for r in monthly_data],
    name="Receita",
    marker_color=COLORS["success"],
    text=[format_brl(r.revenue) for r in monthly_data],
    textposition="outside",
    textfont=dict(size=10, color=COLORS["text_secondary"]),
))

fig_monthly.add_trace(go.Bar(
    x=[r.month_label for r in monthly_data],
    y=[r.expense for r in monthly_data],
    name="Despesa",
    marker_color=COLORS["danger"],
    text=[format_brl(r.expense) for r in monthly_data],
    textposition="outside",
    textfont=dict(size=10, color=COLORS["text_secondary"]),
))

fig_monthly.add_trace(go.Scatter(
    x=[r.month_label for r in monthly_data],
    y=[r.result for r in monthly_data],
    name="Resultado",
    mode="lines+markers+text",
    line=dict(color=COLORS["primary"], width=2),
    marker=dict(size=8, color=COLORS["primary"]),
    text=[format_brl(r.result) for r in monthly_data],
    textposition="top center",
    textfont=dict(size=9, color=COLORS["primary_light"]),
))

fig_monthly.update_layout(
    template=PLOTLY_TEMPLATE,
    barmode="group",
    height=380,
    margin=dict(l=10, r=10, t=20, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title="R$", tickformat=",.0f"),
)

st.plotly_chart(fig_monthly, use_container_width=True)


# ═══════════════════════════════════════════════════════
# ROW 6 — DESPESAS POR CATEGORIA
# ═══════════════════════════════════════════════════════

st.markdown(section_header("Despesas por Categoria", "Mes atual"), unsafe_allow_html=True)

expenses = m["expenses"]

if expenses:
    fig_donut = go.Figure(go.Pie(
        labels=[e.name for e in expenses],
        values=[e.amount for e in expenses],
        hole=0.5,
        textinfo="label+percent",
        textposition="outside",
        textfont=dict(size=11, color=COLORS["text_secondary"]),
        marker=dict(colors=CHART_COLORS[:len(expenses)]),
        outsidetextfont=dict(color=COLORS["text_secondary"]),
    ))

    total_exp = sum(e.amount for e in expenses)
    fig_donut.update_layout(
        template=PLOTLY_TEMPLATE,
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        annotations=[dict(
            text=f"<b>{format_brl(total_exp)}</b>",
            x=0.5, y=0.5,
            font=dict(size=14, color=COLORS["text_primary"], family="JetBrains Mono"),
            showarrow=False,
        )],
    )

    st.plotly_chart(fig_donut, use_container_width=True)
else:
    st.info("Nenhuma despesa registrada no mes atual.")


# ═══════════════════════════════════════════════════════
# ROW 7 — BANCO INTER PJ (condicional)
# ═══════════════════════════════════════════════════════

if INTER_ENABLED:
    st.markdown(section_header("Banco Inter PJ", "Saldo e extrato"), unsafe_allow_html=True)

    inter_balance = None
    inter_statement = None
    inter_error = None

    try:
        with st.spinner("Carregando dados do Banco Inter..."):
            inter_balance, inter_statement = load_inter_data()
    except Exception as e:
        inter_error = str(e)

    if inter_error:
        st.error(f"Erro ao conectar com o Banco Inter: {inter_error}")
        st.info("Verifique se os certificados (.crt/.key) e credenciais estao corretos.")
    else:
        # KPIs do Inter
        ic1, ic2, ic3 = st.columns(3)

        with ic1:
            st.metric(
                label="Saldo Disponivel",
                value=format_brl(inter_balance.disponivel),
            )

        with ic2:
            total_inter = inter_balance.disponivel + inter_balance.bloqueado_cheque + inter_balance.bloqueado_judicial
            st.metric(
                label="Saldo Total (incl. bloqueado)",
                value=format_brl(total_inter),
                help=(
                    f"Disponivel: {format_brl(inter_balance.disponivel)}\n"
                    f"Bloqueado cheque: {format_brl(inter_balance.bloqueado_cheque)}\n"
                    f"Bloqueado judicial: {format_brl(inter_balance.bloqueado_judicial)}"
                ),
            )

        with ic3:
            st.metric(
                label="Transacoes (30d)",
                value=str(len(inter_statement)),
                help="Quantidade de transacoes nos ultimos 30 dias",
            )

        # Extrato
        if inter_statement:
            with st.expander(f"Extrato Banco Inter ({len(inter_statement)} transacoes)", expanded=False):
                extrato_rows = []
                for tx in inter_statement:
                    sinal = "+" if tx.tipo == "CREDITO" else "-"
                    extrato_rows.append({
                        "Data": tx.data.strftime("%d/%m/%Y"),
                        "Tipo": tx.tipo,
                        "Descricao": tx.descricao,
                        "Valor": f"{sinal} {format_brl(tx.valor)}",
                    })
                st.dataframe(
                    pd.DataFrame(extrato_rows),
                    use_container_width=True,
                    hide_index=True,
                )

        # ═══════════════════════════════════════════════════════
        # ROW 8 — CONCILIACAO BANCARIA
        # ═══════════════════════════════════════════════════════

        if inter_statement:
            st.markdown(
                section_header(
                    "Conciliacao Bancaria",
                    "Cruzamento automatico: extrato Inter x contas a pagar/receber Conta Azul",
                ),
                unsafe_allow_html=True,
            )

            recon = reconcile(inter_statement, recv_raw, pay_raw)

            # KPIs de conciliacao
            rc1, rc2, rc3, rc4 = st.columns(4)

            with rc1:
                st.metric(
                    label="Conciliados",
                    value=str(recon.conciliados),
                    help=f"Valor: {format_brl(recon.valor_conciliado)}",
                )

            with rc2:
                st.metric(
                    label="Taxa de Conciliacao",
                    value=format_percent(recon.taxa_conciliacao),
                )

            with rc3:
                st.metric(
                    label="So no Banco",
                    value=str(recon.so_banco),
                    help=f"Valor: {format_brl(recon.valor_so_banco)}",
                )

            with rc4:
                st.metric(
                    label="So no ERP",
                    value=str(recon.so_erp),
                    help=f"Valor: {format_brl(recon.valor_so_erp)}",
                )

            # Tabela de conciliacao
            if recon.items:
                tab_conc, tab_banco, tab_erp = st.tabs([
                    f"Conciliados ({recon.conciliados})",
                    f"So Banco ({recon.so_banco})",
                    f"So ERP ({recon.so_erp})",
                ])

                with tab_conc:
                    conc_items = [i for i in recon.items if i.status == "CONCILIADO"]
                    if conc_items:
                        rows = [{
                            "Data Banco": i.banco_data.strftime("%d/%m/%Y") if i.banco_data else "",
                            "Banco": i.banco_descricao,
                            "Valor Banco": format_brl(i.banco_valor),
                            "ERP": i.erp_descricao,
                            "Valor ERP": format_brl(i.erp_valor),
                        } for i in conc_items]
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhum item conciliado.")

                with tab_banco:
                    banco_items = [i for i in recon.items if i.status == "SO_BANCO"]
                    if banco_items:
                        rows = [{
                            "Data": i.banco_data.strftime("%d/%m/%Y") if i.banco_data else "",
                            "Tipo": i.banco_tipo,
                            "Descricao": i.banco_descricao,
                            "Valor": format_brl(i.banco_valor),
                        } for i in banco_items]
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    else:
                        st.success("Todas as transacoes do banco foram conciliadas!")

                with tab_erp:
                    erp_items = [i for i in recon.items if i.status == "SO_ERP"]
                    if erp_items:
                        rows = [{
                            "Data Vencimento": i.erp_data_vencimento.strftime("%d/%m/%Y") if i.erp_data_vencimento else "",
                            "Descricao": i.erp_descricao,
                            "Valor": format_brl(i.erp_valor),
                        } for i in erp_items]
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    else:
                        st.success("Todos os itens do ERP tem correspondencia no banco!")


# ═══════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════

footer_sources = "Conta Azul"
if INTER_ENABLED:
    footer_sources += " + Banco Inter PJ"
st.markdown(footer(version="v3.0", sources=footer_sources), unsafe_allow_html=True)
