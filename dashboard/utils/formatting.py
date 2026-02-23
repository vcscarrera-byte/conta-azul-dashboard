"""
Utilitários de formatação para valores financeiros brasileiros.
"""


def format_brl(value: float) -> str:
    """Formata um número como Real brasileiro (R$ 150.000,50)."""
    if value >= 0:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_percent(value: float, decimals: int = 1) -> str:
    """Formata um número como percentual (ex: 23.5%)."""
    return f"{value:.{decimals}f}%"


def format_months(value: float) -> str:
    """Formata meses de runway de forma legível."""
    if value <= 0:
        return "0 meses"
    if value >= 99:
        return "99+ meses"
    years = int(value // 12)
    months = int(value % 12)
    if years > 0 and months > 0:
        return f"{years}a {months}m"
    if years > 0:
        return f"{years}a"
    return f"{months}m"
