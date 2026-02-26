"""
Componentes HTML reutilizáveis para o dashboard.
Retornam strings HTML para uso com st.markdown(html, unsafe_allow_html=True).
"""


def dashboard_header(version: str = "v3.0", sources: str = "Conta Azul") -> str:
    """Header principal do dashboard."""
    return f"""
    <div class="dash-header">
        <h1>Dashboard CFO</h1>
        <div class="meta">
            <span>{version}</span>
            <span>&middot;</span>
            <span>Visao financeira consolidada</span>
            <span class="badge">{sources}</span>
        </div>
    </div>
    """


def section_header(title: str, subtitle: str = None) -> str:
    """Header de secao com borda accent."""
    sub_html = f'<div class="sub">{subtitle}</div>' if subtitle else ""
    return f"""
    <div class="section-hdr">
        <h2>{title}</h2>
        {sub_html}
    </div>
    """


def warning_banner(message: str) -> str:
    """Banner de alerta amber."""
    return f'<div class="warn-banner">{message}</div>'


def status_badge(text: str, variant: str = "info") -> str:
    """Badge inline (success, danger, warning, info)."""
    return f'<span class="st-badge {variant}">{text}</span>'


def footer(version: str = "v3.0", sources: str = "Conta Azul") -> str:
    """Footer minimalista."""
    return f"""
    <div class="dash-footer">
        Dashboard CFO {version} &middot; Dados via API {sources} &middot; Atualizacao automatica a cada 5 min
    </div>
    """
