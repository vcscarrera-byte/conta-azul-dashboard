"""
Serviço de Conciliação Bancária.

Cruza transações do extrato do Banco Inter com contas a pagar/receber
do Conta Azul para identificar itens conciliados e pendentes.

Algoritmo de matching:
- Valor exato (tolerância R$0.01)
- Janela de data configurável (padrão: ±3 dias)
- Créditos → recebíveis pagos
- Débitos → pagáveis pagos
"""

from datetime import date, timedelta

from dashboard.config import RECONCILIATION_DATE_TOLERANCE
from dashboard.models.inter_models import (
    InterTransaction,
    ReconciliationItem,
    ReconciliationResult,
)


def _paid_date(item: dict) -> date | None:
    """Extrai data de pagamento/competência de um item do Conta Azul."""
    for field in ("data_pagamento", "data_competencia", "data_vencimento"):
        dt_str = item.get(field)
        if dt_str:
            try:
                return date.fromisoformat(dt_str[:10])
            except (ValueError, TypeError):
                continue
    return None


def _paid_amount(item: dict) -> float:
    """Retorna valor pago de um item do Conta Azul."""
    return float(item.get("pago", item.get("total", 0)) or 0)


def _is_paid(item: dict) -> bool:
    """Verifica se um item do Conta Azul foi pago."""
    status = (item.get("status") or "").upper()
    return status == "PAID"


def _item_description(item: dict) -> str:
    """Extrai descrição legível de um item do Conta Azul."""
    return (
        item.get("descricao")
        or item.get("observacao")
        or item.get("pessoa", {}).get("nome", "")
        or "Sem descrição"
    )


def reconcile(
    transactions: list[InterTransaction],
    receivables: list[dict],
    payables: list[dict],
    tolerance_days: int = RECONCILIATION_DATE_TOLERANCE,
    value_tolerance: float = 0.01,
) -> ReconciliationResult:
    """
    Executa conciliação bancária.

    Args:
        transactions: Transações do extrato Inter
        receivables: Contas a receber do Conta Azul
        payables: Contas a pagar do Conta Azul
        tolerance_days: Janela de tolerância em dias para matching
        value_tolerance: Tolerância de valor para matching (R$)

    Returns:
        ReconciliationResult com itens conciliados e não conciliados
    """
    # Filtrar itens pagos do Conta Azul
    paid_receivables = [r for r in receivables if _is_paid(r)]
    paid_payables = [p for p in payables if _is_paid(p)]

    # Rastrear quais itens do ERP já foram matched
    matched_recv_ids = set()
    matched_pay_ids = set()

    items = []
    conciliados = 0
    so_banco = 0
    valor_conciliado = 0.0
    valor_so_banco = 0.0

    for tx in transactions:
        match_found = False

        # Créditos → buscar em recebíveis pagos
        if tx.tipo == "CREDITO":
            candidates = paid_receivables
            matched_set = matched_recv_ids
        else:
            # Débitos → buscar em pagáveis pagos
            candidates = paid_payables
            matched_set = matched_pay_ids

        for i, item in enumerate(candidates):
            item_id = item.get("id", str(i))
            if item_id in matched_set:
                continue

            erp_amount = _paid_amount(item)
            erp_date = _paid_date(item)

            # Match por valor
            if abs(erp_amount - tx.valor) > value_tolerance:
                continue

            # Match por data
            if erp_date:
                diff = abs((tx.data - erp_date).days)
                if diff > tolerance_days:
                    continue

            # Match encontrado
            matched_set.add(item_id)
            match_found = True

            items.append(ReconciliationItem(
                banco_data=tx.data,
                banco_descricao=tx.descricao,
                banco_valor=tx.valor,
                banco_tipo=tx.tipo,
                erp_descricao=_item_description(item),
                erp_valor=erp_amount,
                erp_data_vencimento=erp_date,
                erp_status="PAID",
                erp_id=item_id,
                status="CONCILIADO",
            ))
            conciliados += 1
            valor_conciliado += tx.valor
            break

        if not match_found:
            items.append(ReconciliationItem(
                banco_data=tx.data,
                banco_descricao=tx.descricao,
                banco_valor=tx.valor,
                banco_tipo=tx.tipo,
                status="SO_BANCO",
            ))
            so_banco += 1
            valor_so_banco += tx.valor

    # Itens do ERP sem match no banco
    so_erp = 0
    valor_so_erp = 0.0

    for source, candidates, matched_set in [
        ("recebível", paid_receivables, matched_recv_ids),
        ("pagável", paid_payables, matched_pay_ids),
    ]:
        for i, item in enumerate(candidates):
            item_id = item.get("id", str(i))
            if item_id in matched_set:
                continue

            erp_amount = _paid_amount(item)
            erp_date = _paid_date(item)

            # Filtrar só itens dentro do período do extrato
            if transactions and erp_date:
                min_date = min(tx.data for tx in transactions) - timedelta(days=tolerance_days)
                max_date = max(tx.data for tx in transactions) + timedelta(days=tolerance_days)
                if erp_date < min_date or erp_date > max_date:
                    continue

            items.append(ReconciliationItem(
                erp_descricao=_item_description(item),
                erp_valor=erp_amount,
                erp_data_vencimento=erp_date,
                erp_status="PAID",
                erp_id=item_id,
                status="SO_ERP",
            ))
            so_erp += 1
            valor_so_erp += erp_amount

    return ReconciliationResult(
        items=items,
        total_transacoes_banco=len(transactions),
        total_itens_erp=len(paid_receivables) + len(paid_payables),
        conciliados=conciliados,
        so_banco=so_banco,
        so_erp=so_erp,
        valor_conciliado=valor_conciliado,
        valor_so_banco=valor_so_banco,
        valor_so_erp=valor_so_erp,
    )
