"""
Design system: Dark Fintech theme.
Tokens de cor, CSS customizado e template Plotly.
"""

# ─── Color Tokens ───

COLORS = {
    # Backgrounds
    "bg_base": "#0f1117",
    "bg_surface": "#1a1d29",
    "bg_elevated": "#222639",
    "border": "#2a2d3a",
    "border_light": "#353849",
    # Text
    "text_primary": "#e8eaed",
    "text_secondary": "#9ca3af",
    "text_muted": "#6b7280",
    # Accent
    "primary": "#6366f1",
    "primary_light": "#818cf8",
    "primary_dim": "rgba(99,102,241,0.12)",
    # Semantic
    "success": "#10b981",
    "success_dim": "rgba(16,185,129,0.12)",
    "danger": "#ef4444",
    "danger_dim": "rgba(239,68,68,0.12)",
    "warning": "#f59e0b",
    "warning_dim": "rgba(245,158,11,0.12)",
    "info": "#3b82f6",
    "info_dim": "rgba(59,130,246,0.12)",
}

CHART_COLORS = [
    COLORS["primary"],
    COLORS["success"],
    COLORS["danger"],
    COLORS["warning"],
    COLORS["info"],
    COLORS["primary_light"],
    "#f472b6",  # pink
    "#a78bfa",  # violet
]

AGING_COLORS = {
    "Vencido": COLORS["danger"],
    "0-30d": COLORS["warning"],
    "31-60d": COLORS["info"],
    "60+d": COLORS["text_muted"],
}


# ─── Plotly Template ───

PLOTLY_TEMPLATE = {
    "layout": {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {
            "family": "Plus Jakarta Sans, sans-serif",
            "color": COLORS["text_secondary"],
            "size": 12,
        },
        "title": {"font": {"color": COLORS["text_primary"], "size": 16}},
        "xaxis": {
            "gridcolor": COLORS["border"],
            "gridwidth": 1,
            "linecolor": COLORS["border"],
            "zerolinecolor": COLORS["border"],
            "tickfont": {"color": COLORS["text_muted"]},
        },
        "yaxis": {
            "gridcolor": COLORS["border"],
            "gridwidth": 1,
            "linecolor": COLORS["border"],
            "zerolinecolor": COLORS["border"],
            "tickfont": {"color": COLORS["text_muted"]},
        },
        "legend": {
            "font": {"color": COLORS["text_secondary"]},
            "bgcolor": "rgba(0,0,0,0)",
        },
        "hoverlabel": {
            "bgcolor": COLORS["bg_elevated"],
            "bordercolor": COLORS["border"],
            "font": {"color": COLORS["text_primary"], "family": "Plus Jakarta Sans"},
        },
        "colorway": CHART_COLORS,
        "margin": {"l": 10, "r": 10, "t": 10, "b": 10},
    }
}


# ─── Custom CSS ───

CUSTOM_CSS = """
<style>
/* ── Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Global ── */
html, body, [data-testid="stAppViewContainer"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 1200px !important;
}

/* ── Metric Cards ── */
[data-testid="stMetric"] {
    background: """ + COLORS["bg_surface"] + """;
    border: 1px solid """ + COLORS["border"] + """;
    border-radius: 12px;
    padding: 20px 16px;
    transition: border-color 0.2s ease;
}
[data-testid="stMetric"]:hover {
    border-color: """ + COLORS["border_light"] + """;
}

[data-testid="stMetricLabel"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    color: """ + COLORS["text_muted"] + """ !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}
[data-testid="stMetricLabel"] > div > div {
    overflow: visible !important;
}

[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.35rem !important;
    font-weight: 600 !important;
    color: """ + COLORS["text_primary"] + """ !important;
}

[data-testid="stMetricDelta"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.8rem !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: """ + COLORS["bg_surface"] + """ !important;
    border-right: 1px solid """ + COLORS["border"] + """ !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.85rem;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: """ + COLORS["bg_surface"] + """;
    border-radius: 10px;
    padding: 4px;
    border: 1px solid """ + COLORS["border"] + """;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    color: """ + COLORS["text_muted"] + """ !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    padding: 8px 16px !important;
    background: transparent !important;
}
.stTabs [aria-selected="true"] {
    background: """ + COLORS["primary_dim"] + """ !important;
    color: """ + COLORS["primary_light"] + """ !important;
}

/* ── DataFrames ── */
[data-testid="stDataFrame"] {
    border: 1px solid """ + COLORS["border"] + """;
    border-radius: 10px;
    overflow: hidden;
}

/* ── Expanders ── */
[data-testid="stExpander"] {
    border: 1px solid """ + COLORS["border"] + """ !important;
    border-radius: 10px !important;
    background: """ + COLORS["bg_surface"] + """ !important;
}
[data-testid="stExpander"] summary {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 500 !important;
    color: """ + COLORS["text_secondary"] + """ !important;
}

/* ── Buttons ── */
.stButton > button {
    border-radius: 8px !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 600 !important;
    border: 1px solid """ + COLORS["border"] + """ !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    border-color: """ + COLORS["primary"] + """ !important;
    color: """ + COLORS["primary_light"] + """ !important;
}

/* ── Dividers ── */
[data-testid="stHorizontalBlock"] hr,
hr {
    border-color: """ + COLORS["border"] + """ !important;
    opacity: 0.5;
}

/* ── Scrollbar ── */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: """ + COLORS["bg_base"] + """;
}
::-webkit-scrollbar-thumb {
    background: """ + COLORS["border_light"] + """;
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: """ + COLORS["text_muted"] + """;
}

/* ── Spinner ── */
.stSpinner > div {
    border-top-color: """ + COLORS["primary"] + """ !important;
}

/* ── Section Header (custom) ── */
.section-hdr {
    margin-top: 1rem;
    margin-bottom: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid """ + COLORS["primary_dim"] + """;
}
.section-hdr h2 {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1.25rem !important;
    color: """ + COLORS["text_primary"] + """ !important;
    margin: 0 !important;
    line-height: 1.3 !important;
}
.section-hdr .sub {
    font-size: 0.8rem;
    color: """ + COLORS["text_muted"] + """;
    margin-top: 2px;
}

/* ── Warning Banner ── */
.warn-banner {
    background: """ + COLORS["warning_dim"] + """;
    border: 1px solid rgba(245,158,11,0.3);
    border-left: 3px solid """ + COLORS["warning"] + """;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 12px;
    font-size: 0.88rem;
    color: """ + COLORS["text_primary"] + """;
    line-height: 1.5;
}

/* ── Dashboard Header ── */
.dash-header {
    padding: 0.5rem 0 1rem 0;
}
.dash-header h1 {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1.75rem !important;
    color: """ + COLORS["text_primary"] + """ !important;
    margin: 0 0 4px 0 !important;
}
.dash-header .meta {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.8rem;
    color: """ + COLORS["text_muted"] + """;
}
.dash-header .badge {
    display: inline-block;
    background: """ + COLORS["primary_dim"] + """;
    color: """ + COLORS["primary_light"] + """;
    font-weight: 600;
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

/* ── Footer ── */
.dash-footer {
    text-align: center;
    padding: 1.5rem 0 0.5rem 0;
    font-size: 0.75rem;
    color: """ + COLORS["text_muted"] + """;
    border-top: 1px solid """ + COLORS["border"] + """;
    margin-top: 1rem;
}

/* ── Status Badge ── */
.st-badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.st-badge.success { background: """ + COLORS["success_dim"] + """; color: """ + COLORS["success"] + """; }
.st-badge.danger  { background: """ + COLORS["danger_dim"] + """; color: """ + COLORS["danger"] + """; }
.st-badge.warning { background: """ + COLORS["warning_dim"] + """; color: """ + COLORS["warning"] + """; }
.st-badge.info    { background: """ + COLORS["info_dim"] + """; color: """ + COLORS["info"] + """; }
</style>
"""
