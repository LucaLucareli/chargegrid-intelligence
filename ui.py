from datetime import datetime
import pandas as pd

from config import CAPACIDADE_TOTAL_KW, LIMIAR_CRITICO_KW, LIMIAR_REDUCAO_KW, POTENCIA_MIN_KW, TIPOS_USUARIO, TIPOS_VEICULO
from models import EstacaoRepository
from algorithms import busca_sequencial, bubble_sort
from services import ServicoRecarga
from protocols import ocpp_boot_notification, ocpp_meter_values, modbus_leitura_medidor

repo = EstacaoRepository()
servico = ServicoRecarga()

def linha(char="-", largura=62):
    print(char * largura)

def cabecalho(titulo: str):
    linha("=")
    print(f"  {titulo}")
    linha("=")

def subcabecalho(titulo: str):
    linha("-")
    print(f"  {titulo}")
    linha("-")

def entrada_inteira(prompt: str, minimo: int, maximo: int) -> int:
    while True:
        try:
            valor = int(input(prompt))
            if minimo <= valor <= maximo:
                return valor
            print(f"     Digite um número entre {minimo} e {maximo}.")
        except ValueError:
            print("     Entrada inválida. Digite apenas números inteiros.")

def entrada_float(prompt: str, minimo: float, maximo: float) -> float:
    while True:
        try:
            valor = float(input(prompt))
            if minimo <= valor <= maximo:
                return valor
            print(f"     Digite um valor entre {minimo:.1f} e {maximo:.1f}.")
        except ValueError:
            print("     Entrada inválida. Use ponto como separador decimal.")

def escolher_opcao(prompt: str, opcoes: dict) -> str:
    for k, v in opcoes.items():
        print(f"    [{k}] {v}")
    while True:
        escolha = input(prompt).strip()
        if escolha in opcoes:
            return escolha
        print(f"     Opção inválida. Escolha entre: {', '.join(opcoes.keys())}.")

def exibir_painel():
    cabecalho("PAINEL DO ELETROPOSTO — ChargeGrid Intelligence")
    demanda  = servico.demanda_atual_kw()
    uso_pct  = demanda / CAPACIDADE_TOTAL_KW * 100
    barra    = int(uso_pct / 5)
    cor      = (
        "CRÍTICO" if demanda >= LIMIAR_CRITICO_KW else
        "ALERTA"  if demanda >= LIMIAR_REDUCAO_KW else
        "NORMAL"
    )

    print(f"\n  Demanda total : {demanda:.2f} kW / {CAPACIDADE_TOTAL_KW:.1f} kW")
    print(f"  Disponível    : {servico.potencia_disponivel_kw():.2f} kW")
    print(f"  Uso           : {'█' * barra:<20} {uso_pct:.1f}%  [{cor}]")
    print(f"  Pontos livres : {servico.pontos_livres()}")
    print(f"  Pontos ativos : {servico.pontos_ocupados()}")

    if servico.pontos_ocupados():
        subcabecalho("Sessões ativas")
        for ponto in servico.pontos_ocupados():
            s = repo.obter_ponto(ponto)
            print(
                f"  Ponto #{ponto} │ {s['id_sessao']} │ {s['tipo_usuario']:<18} │ "
                f"{s['veiculo']['nome']:<20} │ {s['potencia_alocada_kw']:.2f} kW alocados"
            )
    print()

def exibir_relatorio_sessao(sessao: dict, resultado: dict):
    cabecalho(f"RELATÓRIO DE SESSÃO — {sessao['id_sessao']}")

    subcabecalho("Identificação")
    print(f"  ID da Sessão     : {sessao['id_sessao']}")
    print(f"  Ponto            : #{sessao['ponto']}")
    print(f"  Tipo de Usuário  : {sessao['tipo_usuario']}")
    print(f"  Veículo          : {sessao['veiculo']['nome']}")
    print(f"  Capacidade       : {sessao['veiculo']['bateria_kwh']} kWh")

    subcabecalho("Período")
    print(f"  Início           : {resultado['dt_inicio'].strftime('%d/%m/%Y %H:%M')}")
    print(f"  Fim              : {resultado['dt_fim'].strftime('%d/%m/%Y %H:%M')}")
    h, m = divmod(resultado["duracao_min"], 60)
    print(f"  Duração          : {h}h {m:02d}min")

    subcabecalho("Power Management")
    print(f"  Potência solicitada : {sessao['potencia_solicitada']:.2f} kW")
    print(
        f"  Potência alocada    : {sessao['potencia_alocada_kw']:.2f} kW "
        f"({sessao.get('fator_reducao', 1.0)*100:.0f}%)"
    )
    print(f"  Motivo              : {sessao.get('motivo_reducao', 'N/A')}")

    subcabecalho("Energia")
    print(f"  SOC Inicial      : {sessao['carga_inicial']:.1f}%")
    print(f"  SOC Final        : {sessao['carga_alvo']:.1f}%")
    print(f"  Energia Total    : {resultado['energia_total']:.3f} kWh")
    print(f"  Potência Média   : {resultado['potencia_media']:.2f} kW")

    subcabecalho("Tarifação Dinâmica")
    periodo_label = {
        "ponta":    "Horário de Ponta (18h–20h)",
        "off-peak": "Fora de Ponta / Madrugada (0h–5h)",
        "normal":   "Horário Normal",
    }[resultado["periodo"]]
    print(f"  Período          : {periodo_label}")
    print(f"  Tarifa aplicada  : R$ {resultado['tarifa_kwh']:.4f}/kWh")
    if resultado["acrescimo_kwh"] > 0:
        print(f"  Acréscimo demanda: +R$ {resultado['acrescimo_kwh']:.4f}/kWh (+10%)")
    if resultado["desconto_label"]:
        print(f"  Regra especial   : {resultado['desconto_label']}")

    subcabecalho("Cobrança")
    print(f"  Custo de Energia : R$ {resultado['custo_energia']:>8.2f}")
    if resultado["desconto"] > 0:
        print(f"  Desconto (15%)   : R$ {resultado['desconto']:>8.2f} –")
    print(f"  Taxa de Serviço  : R$ {resultado['taxa_servico']:>8.2f}")
    linha("-")
    print(f"  TOTAL A PAGAR    : R$ {resultado['total']:>8.2f}")

    subcabecalho("Impacto Estimado")
    print(f"  CO₂ Evitado      : {resultado['co2_evitado']:.2f} kg")
    print(f"  Autonomia Ganha  : ~{resultado['km_estimado']:.0f} km")

    linha("=")
    print("  Sessão encerrada com sucesso. Protocolo OCPP 1.6 registrado.")
    linha("=")
    print()

def exibir_relatorio_consolidado():
    historico = repo.obter_historico()
    if not historico:
        print("\n  Nenhuma sessão encerrada até o momento.\n")
        return

    cabecalho("RELATÓRIO CONSOLIDADO — ChargeGrid Intelligence")
    total_energia = 0.0
    total_receita = 0.0
    total_co2     = 0.0
    total_km      = 0.0

    print(f"\n  {'ID Sessão':<22} {'Ponto':<7} {'Usuário':<20} {'kWh':>7} {'R$':>8}")
    linha()

    for s in historico:
        r = s.resultado
        if not r:
            continue
        print(
            f"  {s.id_sessao:<22} #{s.ponto:<6} {s.tipo_usuario:<20} "
            f"{r['energia_total']:>7.3f} {r['total']:>8.2f}"
        )
        total_energia += r["energia_total"]
        total_receita += r["total"]
        total_co2     += r["co2_evitado"]
        total_km      += r["km_estimado"]

    linha()
    print(f"\n  Sessões encerradas : {len(historico)}")
    print(f"  Energia total      : {total_energia:.3f} kWh")
    print(f"  Receita total      : R$ {total_receita:.2f}")
    print(f"  CO₂ evitado total  : {total_co2:.2f} kg")
    print(f"  Autonomia gerada   : {total_km:.0f} km")
    linha("=")
    print()

def exportar_relatorio_excel():
    historico = repo.obter_historico()
    if not historico:
        print("\n  Nenhuma sessão encerrada para exportar.\n")
        return

    dados = []
    for sessao in historico:
        resultado = sessao.resultado
        if not resultado:
            continue
        dados.append({
            "ID Sessão": sessao.id_sessao,
            "Ponto": sessao.ponto,
            "Usuário": sessao.tipo_usuario,
            "Veículo": sessao.veiculo["nome"],
            "SOC Inicial (%)": sessao.carga_inicial,
            "SOC Final (%)": sessao.carga_alvo,
            "Potência Solicitada (kW)": sessao.potencia_solicitada,
            "Potência Alocada (kW)": sessao.potencia_alocada_kw,
            "Energia Consumida (kWh)": sessao.energia,
            "Duração (min)": sessao.tempo,
            "Tarifa (R$/kWh)": resultado["tarifa_kwh"],
            "Valor Total (R$)": sessao.custo,
            "CO2 Evitado (kg)": resultado["co2_evitado"],
            "Autonomia Gerada (km)": resultado["km_estimado"],
            "Início": resultado["dt_inicio"].strftime("%d/%m/%Y %H:%M"),
            "Fim": resultado["dt_fim"].strftime("%d/%m/%Y %H:%M")
        })

    df = pd.DataFrame(dados)
    nome_arquivo = f"relatorio_chargegrid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(nome_arquivo, index=False)
    print(f"\n  Relatório exportado com sucesso!")
    print(f"  Arquivo: {nome_arquivo}\n")

def coletar_dados_sessao() -> dict | None:
    livres = servico.pontos_livres()
    if not livres:
        print("\n     Todos os pontos estão ocupados. Encerre uma sessão primeiro.\n")
        return None

    print(f"\n  Pontos disponíveis: {livres}")
    ponto = entrada_inteira(
        f"  Selecione o ponto de carregamento [{livres[0]}–{livres[-1]}]: ",
        min(livres), max(livres),
    )
    if ponto not in livres:
        print(f"\n     Ponto #{ponto} está ocupado.\n")
        return None

    print("\n  Tipo de usuário:")
    chave_usuario = escolher_opcao("\n  Escolha [1/2/3]: ", TIPOS_USUARIO)
    tipo_usuario  = TIPOS_USUARIO[chave_usuario]

    print("\n  Tipo de veículo:")
    chave_veiculo = escolher_opcao(
        "\n  Escolha [1/2/3/4]: ",
        {k: f"{v['nome']} (bat.: {v['bateria_kwh']} kWh)" for k, v in TIPOS_VEICULO.items()},
    )
    veiculo = TIPOS_VEICULO[chave_veiculo]

    print()
    carga_inicial = entrada_float("  SOC atual          [%] [0–99]: ", 0, 99)
    carga_alvo    = entrada_float(
        f"  SOC desejado       [%] [{carga_inicial+1:.0f}–100]: ",
        carga_inicial + 1, 100,
    )
    pot_max     = veiculo["potencia_max"]
    potencia_kw = entrada_float(
        f"  Potência desejada [kW] [{POTENCIA_MIN_KW}–{pot_max}]: ",
        POTENCIA_MIN_KW, pot_max,
    )
    hora_inicio = entrada_inteira("  Hora de início     [h] [0–23]: ", 0, 23)

    return {
        "ponto":               ponto,
        "tipo_usuario":        tipo_usuario,
        "veiculo":             veiculo,
        "carga_inicial":       carga_inicial,
        "carga_alvo":          carga_alvo,
        "potencia_kw":         potencia_kw,
        "hora_inicio":         hora_inicio,
        "demanda_no_inicio_kw": servico.demanda_atual_kw(),
    }


def menu_iniciar_sessao():
    dados = coletar_dados_sessao()
    if not dados:
        return
    ponto     = dados["ponto"]
    id_sessao = servico.iniciar_sessao(ponto, dados)
    s         = repo.obter_ponto(ponto)
    print(f"\n    Sessão {id_sessao} iniciada no Ponto #{ponto}")
    print(f"    Potência alocada : {s['potencia_alocada_kw']:.2f} kW")
    print(f"    Motivo           : {s['motivo_reducao']}\n")

def menu_encerrar_sessao():
    ocupados = servico.pontos_ocupados()
    if not ocupados:
        print("\n  Nenhum ponto ativo para encerrar.\n")
        return
    print(f"\n  Pontos com sessão ativa: {ocupados}")
    ponto = entrada_inteira(
        f"  Selecione o ponto a encerrar [{ocupados[0]}–{ocupados[-1]}]: ",
        min(ocupados), max(ocupados),
    )
    if ponto not in ocupados:
        print(f"\n     Ponto #{ponto} não possui sessão ativa.\n")
        return
    print(f"\n  Processando sessão do Ponto #{ponto}...")
    snapshot  = {**repo.obter_ponto(ponto)}
    resultado = servico.encerrar_sessao(ponto)
    exibir_relatorio_sessao(snapshot, resultado)

def menu_buscar_sessao():
    cabecalho("BUSCA DE SESSÃO")
    historico = repo.obter_historico()
    if not historico:
        print("\n  Nenhuma sessão registrada no histórico.\n")
        return
    
    id_procurado = input("  Digite o ID da sessão procurada (ex: CG-YYYYMMDD-0001): ").strip()
    indice = busca_sequencial(historico, id_procurado)
    
    if indice != -1:
        sessao_encontrada = historico[indice]
        dict_fake = {
            "id_sessao": sessao_encontrada.id_sessao,
            "ponto": sessao_encontrada.ponto,
            "tipo_usuario": sessao_encontrada.tipo_usuario,
            "veiculo": sessao_encontrada.veiculo,
            "carga_inicial": sessao_encontrada.carga_inicial,
            "carga_alvo": sessao_encontrada.carga_alvo,
            "potencia_solicitada": sessao_encontrada.potencia_solicitada,
            "potencia_alocada_kw": sessao_encontrada.potencia_alocada_kw,
            "fator_reducao": sessao_encontrada.resultado.get("fator_reducao", 1.0),
            "motivo_reducao": sessao_encontrada.resultado.get("motivo_reducao", "N/A"),
        }
        exibir_relatorio_sessao(dict_fake, sessao_encontrada.resultado)
    else:
        print(f"\n     Sessão {id_procurado} não encontrada!\n")

def menu_ordenar_sessoes():
    cabecalho("ORDENAR HISTÓRICO DE SESSÕES")
    historico = repo.obter_historico()
    if not historico:
        print("\n  Nenhuma sessão registrada no histórico para ordenar.\n")
        return
    
    print("  Escolha o critério de ordenação:")
    print("  1 - ID")
    print("  2 - Energia consumida")
    print("  3 - Custo da sessão")
    print("  4 - Tempo de recarga")
    
    criterio = input("\n  Opção [1-4]: ").strip()
    if criterio not in ["1", "2", "3", "4"]:
        print("  Opção inválida.")
        return
        
    bubble_sort(historico, criterio)
    print("\n  Sessões ordenadas com sucesso! Utilize a opção de listar para visualizar.\n")

def menu_estatisticas():
    cabecalho("ESTATÍSTICAS DA ESTAÇÃO")
    historico = repo.obter_historico()
    qtd = len(historico)
    if qtd == 0:
        print("\n  Nenhuma sessão realizada até o momento.\n")
        return

    energia_total = 0.0
    faturamento = 0.0
    maior_consumo = -1.0
    menor_consumo = float('inf')

    for s in historico:
        energia_total += s.energia
        faturamento += s.custo
        if s.energia > maior_consumo:
            maior_consumo = s.energia
        if s.energia < menor_consumo:
            menor_consumo = s.energia

    ticket_medio = faturamento / qtd if qtd > 0 else 0.0

    print(f"  Sessões realizadas : {qtd}")
    print(f"  Energia fornecida  : {energia_total:.2f} kWh")
    print(f"  Faturamento total  : R$ {faturamento:.2f}")
    print(f"  Ticket médio       : R$ {ticket_medio:.2f}")
    print(f"  Maior consumo      : {maior_consumo:.2f} kWh")
    print(f"  Menor consumo      : {menor_consumo:.2f} kWh\n")

def cenario_multiplos_veiculos():
    cabecalho("CENÁRIO AUTOMÁTICO — 3 Veículos Simultâneos")
    print("""
  Este cenário demonstra:
    • Conexão de 3 veículos em pontos distintos
    • Redução automática de potência por Power Management
    • Tarifação dinâmica (ponta / alta demanda)
    • Telemetria OCPP e leitura MODBUS
    • Encerramento sequencial com relatório consolidado
""")
    input("  Pressione ENTER para iniciar o cenário...")

    veiculos_cenario = [
        {
            "ponto": 1, "tipo_usuario": "Assinante",
            "veiculo": TIPOS_VEICULO["2"],
            "carga_inicial": 20, "carga_alvo": 80,
            "potencia_kw": 11.0, "hora_inicio": 19,
        },
        {
            "ponto": 2, "tipo_usuario": "Visitante",
            "veiculo": TIPOS_VEICULO["1"],
            "carga_inicial": 10, "carga_alvo": 90,
            "potencia_kw": 7.4, "hora_inicio": 19,
        },
        {
            "ponto": 3, "tipo_usuario": "Frota Corporativa",
            "veiculo": TIPOS_VEICULO["3"],
            "carga_inicial": 30, "carga_alvo": 95,
            "potencia_kw": 22.0, "hora_inicio": 19,
        },
    ]

    subcabecalho("Passo 1 — Boot dos Carregadores")
    for v in veiculos_cenario:
        ocpp_boot_notification(v["ponto"])

    input("\n  Pressione ENTER para conectar os veículos...")

    subcabecalho("Passo 2 — Início das Sessões")
    for v in veiculos_cenario:
        v["demanda_no_inicio_kw"] = servico.demanda_atual_kw()
        id_sessao = servico.iniciar_sessao(v["ponto"], v)
        s         = repo.obter_ponto(v["ponto"])
        print(f"\n    Ponto #{v['ponto']} — {id_sessao}")
        print(f"    Usuário  : {v['tipo_usuario']}")
        print(f"    Veículo  : {v['veiculo']['nome']}")
        print(
            f"    Potência : {v['potencia_kw']:.1f} kW solicitados → "
            f"{s['potencia_alocada_kw']:.1f} kW alocados  ({s['motivo_reducao']})"
        )

    exibir_painel()
    input("  Pressione ENTER para simular telemetria MODBUS...")

    subcabecalho("Passo 3 — Telemetria Periódica (MeterValues + MODBUS)")
    for ponto in servico.pontos_ocupados():
        s    = repo.obter_ponto(ponto)
        pot  = s["potencia_alocada_kw"]
        kwh  = pot * 0.25
        soc  = s["carga_inicial"] + 5
        ocpp_meter_values(s["id_sessao"], ponto, soc, kwh, pot)
        modbus_leitura_medidor(ponto, pot, kwh)

    input("\n  Pressione ENTER para encerrar as sessões e gerar relatórios...")

    subcabecalho("Passo 4 — Encerramento das Sessões")
    for v in veiculos_cenario:
        snapshot  = {**repo.obter_ponto(v["ponto"])}
        resultado = servico.encerrar_sessao(v["ponto"], verbose=False)
        exibir_relatorio_sessao(snapshot, resultado)

    exibir_relatorio_consolidado()

