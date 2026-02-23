"""
Módulo financeiro - Contas a Pagar, Contas a Receber, Categorias, etc.
Usa a Financial API v2 da Conta Azul.
Base URL: https://api-v2.contaazul.com/v1
"""

from client import ContaAzulClient


class Financeiro:
    def __init__(self, client: ContaAzulClient = None):
        self.client = client or ContaAzulClient()

    # ─── Categorias ───

    def listar_categorias(self, pagina=1, tamanho_pagina=50):
        """Lista categorias financeiras (receitas/despesas)."""
        return self.client.get(
            "/categorias",
            params={"pagina": pagina, "tamanho_pagina": tamanho_pagina},
        )

    def listar_categorias_dre(self, pagina=1, tamanho_pagina=50):
        """Lista categorias DRE."""
        return self.client.get(
            "/financeiro/categorias-dre",
            params={"pagina": pagina, "tamanho_pagina": tamanho_pagina},
        )

    # ─── Centros de Custo ───

    def listar_centros_custo(self, pagina=1, tamanho_pagina=50):
        """Lista centros de custo."""
        return self.client.get(
            "/centro-de-custo",
            params={"pagina": pagina, "tamanho_pagina": tamanho_pagina},
        )

    def criar_centro_custo(self, dados):
        """Cria um novo centro de custo."""
        return self.client.post("/centro-de-custo", data=dados)

    # ─── Contas Financeiras ───

    def listar_contas_financeiras(self, pagina=1, tamanho_pagina=50):
        """Lista contas financeiras (bancárias)."""
        return self.client.get(
            "/conta-financeira",
            params={"pagina": pagina, "tamanho_pagina": tamanho_pagina},
        )

    def obter_saldo_conta(self, id_conta_financeira):
        """Obtém saldo atual de uma conta financeira."""
        return self.client.get(
            f"/conta-financeira/{id_conta_financeira}/saldo-atual"
        )

    # ─── Contas a Receber ───

    def listar_recebimentos(
        self, data_vencimento_de, data_vencimento_ate, pagina=1, tamanho_pagina=50
    ):
        """
        Lista contas a receber.

        Args:
            data_vencimento_de: Data início (formato: YYYY-MM-DD). Obrigatório.
            data_vencimento_ate: Data fim (formato: YYYY-MM-DD). Obrigatório.
        """
        return self.client.get(
            "/financeiro/eventos-financeiros/contas-a-receber/buscar",
            params={
                "data_vencimento_de": data_vencimento_de,
                "data_vencimento_ate": data_vencimento_ate,
                "pagina": pagina,
                "tamanho_pagina": tamanho_pagina,
            },
        )

    def criar_recebimento(self, dados):
        """
        Cria uma nova conta a receber.

        Consulte a documentação para o formato correto:
        https://developers.contaazul.com/docs/financial-apis-openapi/v1
        """
        return self.client.post(
            "/financeiro/eventos-financeiros/contas-a-receber", data=dados
        )

    # ─── Contas a Pagar ───

    def listar_pagamentos(
        self, data_vencimento_de, data_vencimento_ate, pagina=1, tamanho_pagina=50
    ):
        """
        Lista contas a pagar.

        Args:
            data_vencimento_de: Data início (formato: YYYY-MM-DD). Obrigatório.
            data_vencimento_ate: Data fim (formato: YYYY-MM-DD). Obrigatório.
        """
        return self.client.get(
            "/financeiro/eventos-financeiros/contas-a-pagar/buscar",
            params={
                "data_vencimento_de": data_vencimento_de,
                "data_vencimento_ate": data_vencimento_ate,
                "pagina": pagina,
                "tamanho_pagina": tamanho_pagina,
            },
        )

    def criar_pagamento(self, dados):
        """
        Cria uma nova conta a pagar.

        Consulte a documentação para o formato correto:
        https://developers.contaazul.com/docs/financial-apis-openapi/v1
        """
        return self.client.post(
            "/financeiro/eventos-financeiros/contas-a-pagar", data=dados
        )

    # ─── Parcelas ───

    def obter_parcelas(self, id_evento):
        """Retorna as parcelas de um evento financeiro."""
        return self.client.get(
            f"/financeiro/eventos-financeiros/{id_evento}/parcelas"
        )

    def atualizar_parcela(self, id_parcela, dados):
        """Atualiza uma parcela (ex: dar baixa)."""
        return self.client.put(
            f"/financeiro/eventos-financeiros/parcelas/{id_parcela}",
            data=dados,
        )
