"""
Exemplo de uso da integração com a API da Conta Azul.

Passo a passo:
1. Copie .env.example para .env e preencha suas credenciais
2. Execute: python exemplo.py
3. Autorize no navegador (primeiro uso)
4. A partir daí, o token é salvo em token.json e renovado automaticamente
"""

from auth import ContaAzulAuth
from client import ContaAzulClient
from financeiro import Financeiro


def main():
    # 1. Autenticação
    auth = ContaAzulAuth()

    # Tenta usar token existente, senão inicia fluxo OAuth2
    try:
        auth.get_access_token()
        print("Token existente carregado com sucesso!")
    except ValueError:
        print("Nenhum token encontrado. Iniciando autorização...\n")
        auth.authorize_interactive()

    # 2. Criar cliente e módulo financeiro
    client = ContaAzulClient(auth)
    fin = Financeiro(client)

    # 3. Exemplos de uso

    # --- Listar categorias financeiras ---
    print("\n=== Categorias Financeiras ===")
    try:
        result = fin.listar_categorias(tamanho_pagina=5)
        itens = result.get("itens", [])
        print(f"Total: {result.get('itens_totais', 0)} categorias")
        for cat in itens:
            print(f"  [{cat['tipo']}] {cat['nome']}")
    except Exception as e:
        print(f"  Erro: {e}")

    # --- Listar contas financeiras ---
    print("\n=== Contas Financeiras ===")
    try:
        result = fin.listar_contas_financeiras(tamanho_pagina=5)
        itens = result.get("itens", [])
        print(f"Total: {result.get('itens_totais', 0)} contas")
        for conta in itens:
            print(f"  {conta.get('nome', 'N/A')} (id: {conta['id']})")
    except Exception as e:
        print(f"  Erro: {e}")

    # --- Listar contas a receber (últimos 3 meses) ---
    print("\n=== Contas a Receber ===")
    try:
        result = fin.listar_recebimentos(
            data_vencimento_de="2025-12-01",
            data_vencimento_ate="2026-02-28",
            tamanho_pagina=5,
        )
        itens = result.get("itens", [])
        print(f"Total: {result.get('itens_totais', 0)}")
        for r in itens:
            print(f"  {r.get('descricao', 'N/A')} | R$ {r.get('valor', 0)}")
    except Exception as e:
        print(f"  Erro: {e}")

    # --- Listar contas a pagar (últimos 3 meses) ---
    print("\n=== Contas a Pagar ===")
    try:
        result = fin.listar_pagamentos(
            data_vencimento_de="2025-12-01",
            data_vencimento_ate="2026-02-28",
            tamanho_pagina=5,
        )
        itens = result.get("itens", [])
        print(f"Total: {result.get('itens_totais', 0)}")
        for p in itens:
            print(f"  {p.get('descricao', 'N/A')} | R$ {p.get('valor', 0)}")
    except Exception as e:
        print(f"  Erro: {e}")


if __name__ == "__main__":
    main()
