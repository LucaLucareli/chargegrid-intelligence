"""
==================================================================
        ChargeGrid Intelligence — Sistema de Gerenciamento
                       Sprint 3 — FIAP
==================================================================
"""

from collections import OrderedDict
from ui import (
    cabecalho, subcabecalho, 
    menu_iniciar_sessao, menu_encerrar_sessao, exibir_painel,
    exibir_relatorio_consolidado, menu_buscar_sessao,
    menu_ordenar_sessoes, menu_estatisticas, cenario_multiplos_veiculos,
    exportar_relatorio_excel
)

MENU_PRINCIPAL = OrderedDict([
    ("1", "Iniciar nova sessão de recarga"),
    ("2", "Encerrar sessão ativa"),
    ("3", "Painel do eletroposto"),
    ("4", "Listar histórico de sessões"),
    ("5", "Buscar sessão (Busca Sequencial)"),
    ("6", "Ordenar sessões (Bubble Sort)"),
    ("7", "Estatísticas da estação"),
    ("8", "Executar cenário automático (3 veículos)"),
    ("9", "Exportar relatório Excel"),
    ("0", "Sair"),
])

ACOES_MENU = {
    "1": menu_iniciar_sessao,
    "2": menu_encerrar_sessao,
    "3": exibir_painel,
    "4": exibir_relatorio_consolidado,
    "5": menu_buscar_sessao,
    "6": menu_ordenar_sessoes,
    "7": menu_estatisticas,
    "8": cenario_multiplos_veiculos,
    "9": exportar_relatorio_excel,
}

def main():
    print()
    cabecalho("ChargeGrid Intelligence v2.0 — FIAP Sprint 3")
    print("""
  Sistema de Gerenciamento Inteligente de Recarga de VEs.
  Controle simultâneo de múltiplos pontos com Power Management,
  tarifação dinâmica, simulação de protocolo OCPP 1.6 / MODBUS,
  algoritmos de busca e ordenação em arquitetura MVC (Model-View-Controller).
""")

    while True:
        subcabecalho("MENU PRINCIPAL")
        for k, v in MENU_PRINCIPAL.items():
            print(f"  [{k}] {v}")
        opcao = input("\n  Escolha uma opção: ").strip()

        if opcao == "0":
            print("\n  Encerrando ChargeGrid Intelligence. Até logo!\n")
            break
        elif opcao in ACOES_MENU:
            ACOES_MENU[opcao]()
        else:
            print("\n     Opção inválida. Escolha entre 0 e 9.\n")


if __name__ == "__main__":
    main()