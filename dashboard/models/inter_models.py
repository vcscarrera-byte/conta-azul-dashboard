"""
Modelos de dados do Banco Inter PJ.
Dataclasses tipadas para saldo, extrato e conciliação bancária.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# ─── Saldo ───

@dataclass
class InterBalance:
    """Saldo da conta corrente no Banco Inter."""
    disponivel: float = 0.0
    bloqueado_cheque: float = 0.0
    bloqueado_judicial: float = 0.0
    limite: float = 0.0


# ─── Extrato ───

@dataclass
class InterTransaction:
    """Transação do extrato bancário."""
    data: date
    tipo: str  # "CREDITO" ou "DEBITO"
    descricao: str
    valor: float
    titulo: str = ""
    numero_documento: str = ""


# ─── Conciliação ───

@dataclass
class ReconciliationItem:
    """Um item da conciliação bancária."""
    # Dados do banco (Inter)
    banco_data: Optional[date] = None
    banco_descricao: str = ""
    banco_valor: float = 0.0
    banco_tipo: str = ""  # CREDITO / DEBITO

    # Dados do ERP (Conta Azul)
    erp_descricao: str = ""
    erp_valor: float = 0.0
    erp_data_vencimento: Optional[date] = None
    erp_status: str = ""
    erp_id: str = ""

    # Status da conciliação
    status: str = ""  # CONCILIADO, SO_BANCO, SO_ERP


@dataclass
class ReconciliationResult:
    """Resultado consolidado da conciliação bancária."""
    items: list[ReconciliationItem] = field(default_factory=list)
    total_transacoes_banco: int = 0
    total_itens_erp: int = 0
    conciliados: int = 0
    so_banco: int = 0
    so_erp: int = 0
    valor_conciliado: float = 0.0
    valor_so_banco: float = 0.0
    valor_so_erp: float = 0.0

    @property
    def taxa_conciliacao(self) -> float:
        """Percentual de transações do banco conciliadas."""
        if self.total_transacoes_banco == 0:
            return 100.0
        return (self.conciliados / self.total_transacoes_banco) * 100
