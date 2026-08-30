import random
from datetime import datetime, timedelta

from config import (
    CAPACIDADE_TOTAL_KW, LIMIAR_CRITICO_KW, LIMIAR_REDUCAO_KW, POTENCIA_MIN_KW, 
    POTENCIA_MAX_PONTO_KW, TARIFA_PONTA_KWH, TARIFA_OFF_PEAK_KWH, TARIFA_PADRAO_KWH, 
    ACRESCIMO_ALTA_DEMANDA, DESCONTO_ASSINANTE, TAXA_SERVICO
)
from models import EstacaoRepository, Sessao
from protocols import ocpp_start_transaction, ocpp_stop_transaction
from ui import subcabecalho # We need this for verbose simulation

class ServicoRecarga:
    """
    Facade que gerencia as operações de recarga, orquestrando as regras de negócio.
    """
    def __init__(self):
        self.repo = EstacaoRepository()

    def demanda_atual_kw(self) -> float:
        return sum(
            s["potencia_alocada_kw"]
            for s in self.repo.pontos.values()
            if s is not None
        )

    def potencia_disponivel_kw(self) -> float:
        return max(0.0, CAPACIDADE_TOTAL_KW - self.demanda_atual_kw())

    def pontos_livres(self) -> list:
        return [p for p, s in self.repo.pontos.items() if s is None]

    def pontos_ocupados(self) -> list:
        return [p for p, s in self.repo.pontos.items() if s is not None]

    def calcular_alocacao(self, potencia_solicitada_kw: float) -> tuple:
        demanda = self.demanda_atual_kw()
        if demanda >= LIMIAR_CRITICO_KW:
            fator  = 0.50
            motivo = "restrição crítica (>95% da capacidade)"
        elif demanda >= LIMIAR_REDUCAO_KW:
            fator  = 0.70
            motivo = "redução preventiva (>80% da capacidade)"
        else:
            fator  = 1.00
            motivo = "capacidade normal"

        alocado = min(potencia_solicitada_kw * fator, self.potencia_disponivel_kw())
        alocado = max(POTENCIA_MIN_KW, alocado) if alocado >= POTENCIA_MIN_KW else 0.0
        return alocado, fator, motivo

    def gerar_id_sessao(self) -> str:
        id_num = self.repo.gerar_proximo_id()
        return f"CG-{datetime.now().strftime('%Y%m%d')}-{id_num:04d}"

    def iniciar_sessao(self, ponto: int, dados: dict) -> str:
        potencia_solicitada        = dados["potencia_kw"]
        alocada, fator, motivo     = self.calcular_alocacao(potencia_solicitada)
        id_sessao                  = self.gerar_id_sessao()

        hora      = dados["hora_inicio"]
        dt_inicio = datetime.now().replace(hour=hora, minute=0, second=0, microsecond=0)

        sessao_dict = {
            "id_sessao":            id_sessao,
            "ponto":                ponto,
            "tipo_usuario":         dados["tipo_usuario"],
            "veiculo":              dados["veiculo"],
            "carga_inicial":        dados["carga_inicial"],
            "carga_alvo":           dados["carga_alvo"],
            "potencia_solicitada":  potencia_solicitada,
            "potencia_alocada_kw":  alocada,
            "fator_reducao":        fator,
            "motivo_reducao":       motivo,
            "hora_inicio":          hora,
            "dt_inicio":            dt_inicio,
            "demanda_no_inicio_kw": dados.get("demanda_no_inicio_kw", 0.0),
            "status":               "Carregando",
        }

        self.repo.atualizar_ponto(ponto, sessao_dict)
        ocpp_start_transaction(id_sessao, ponto, dados)
        return id_sessao

    def encerrar_sessao(self, ponto: int, verbose=False) -> dict | None:
        sessao = self.repo.obter_ponto(ponto)
        if not sessao:
            return None

        resultado = self.processar_sessao(sessao, verbose)
        sessao["resultado"] = resultado
        sessao["status"]    = "Encerrada"

        ocpp_stop_transaction(sessao, resultado)

        nova_sessao = Sessao(
            id_sessao=sessao["id_sessao"],
            ponto=sessao["ponto"],
            tipo_usuario=sessao["tipo_usuario"],
            veiculo=sessao["veiculo"],
            carga_inicial=sessao["carga_inicial"],
            carga_alvo=sessao["carga_alvo"],
            potencia_solicitada=sessao["potencia_solicitada"],
            potencia_alocada=sessao["potencia_alocada_kw"],
            resultado=resultado
        )
        self.repo.adicionar_ao_historico(nova_sessao)
        self.repo.atualizar_ponto(ponto, None)
        return resultado

    def detectar_horario(self, hora: int) -> str:
        if 18 <= hora <= 20:
            return "ponta"
        elif 0 <= hora <= 5:
            return "off-peak"
        return "normal"

    def calcular_tarifa(self, hora: int, tipo_usuario: str, demanda_kw: float) -> tuple:
        periodo = self.detectar_horario(hora)
        base    = {
            "ponta":    TARIFA_PONTA_KWH,
            "off-peak": TARIFA_OFF_PEAK_KWH,
            "normal":   TARIFA_PADRAO_KWH,
        }[periodo]

        if tipo_usuario == "Frota Corporativa":
            tarifa        = min(base, TARIFA_OFF_PEAK_KWH)
            desconto_label = "Tarifa negociada (teto off-peak)"
        else:
            tarifa        = base
            desconto_label = ""

        acrescimo = 0.0
        if demanda_kw > LIMIAR_REDUCAO_KW and tipo_usuario != "Frota Corporativa":
            acrescimo = tarifa * ACRESCIMO_ALTA_DEMANDA
            tarifa   += acrescimo

        return tarifa, periodo, desconto_label, acrescimo

    def simular_recarga_silenciosa(self, potencia_kw: float, carga_inicial: float, carga_alvo: float, capacidade_bateria: float) -> tuple:
        energia_necessaria = (carga_alvo - carga_inicial) / 100 * capacidade_bateria
        energia_carregada  = 0.0
        minuto             = 0
        registros          = []

        while energia_carregada < energia_necessaria:
            variacao       = random.uniform(-0.05, 0.05)
            potencia_atual = max(
                POTENCIA_MIN_KW,
                min(potencia_kw * (1 + variacao), POTENCIA_MAX_PONTO_KW)
            )
            energia_ciclo     = min(potencia_atual / 60, energia_necessaria - energia_carregada)
            energia_carregada += energia_ciclo
            soc_atual          = carga_inicial + (energia_carregada / capacidade_bateria) * 100
            minuto            += 1
            registros.append({
                "minuto":     minuto,
                "potencia_kw": round(potencia_atual, 2),
                "energia_kwh": round(energia_ciclo, 4),
                "soc":         round(soc_atual, 1),
            })

        return registros, energia_carregada

    def simular_recarga_verbose(self, potencia_kw: float, carga_inicial: float, carga_alvo: float, capacidade_bateria: float) -> tuple:
        energia_necessaria = (carga_alvo - carga_inicial) / 100 * capacidade_bateria
        energia_carregada  = 0.0
        minuto             = 0
        registros          = []

        print()
        subcabecalho("Simulação em progresso...")
        print(f"  Energia a carregar: {energia_necessaria:.2f} kWh")
        print()

        while energia_carregada < energia_necessaria:
            variacao       = random.uniform(-0.05, 0.05)
            potencia_atual = max(
                POTENCIA_MIN_KW,
                min(potencia_kw * (1 + variacao), POTENCIA_MAX_PONTO_KW)
            )
            energia_ciclo     = min(potencia_atual / 60, energia_necessaria - energia_carregada)
            energia_carregada += energia_ciclo
            soc_atual          = carga_inicial + (energia_carregada / capacidade_bateria) * 100
            minuto            += 1
            registros.append({
                "minuto":     minuto,
                "potencia_kw": round(potencia_atual, 2),
                "energia_kwh": round(energia_ciclo, 4),
                "soc":         round(soc_atual, 1),
            })
            if minuto % 5 == 0 or energia_carregada >= energia_necessaria:
                barra = int(soc_atual / 5)
                print(
                    f"  t={minuto:>4}min │ {potencia_atual:>5.2f} kW │ "
                    f"SOC: {'█' * barra:<20} {soc_atual:>5.1f}%"
                )

        return registros, energia_carregada

    def processar_sessao(self, sessao: dict, verbose: bool = False) -> dict:
        veiculo      = sessao["veiculo"]
        tipo_usuario = sessao["tipo_usuario"]
        hora_inicio  = sessao["hora_inicio"]
        potencia     = sessao["potencia_alocada_kw"]

        fn_simular = self.simular_recarga_verbose if verbose else self.simular_recarga_silenciosa
        registros, energia_total = fn_simular(
            potencia_kw        = potencia,
            carga_inicial      = sessao["carga_inicial"],
            carga_alvo         = sessao["carga_alvo"],
            capacidade_bateria = veiculo["bateria_kwh"],
        )

        duracao_min    = len(registros)
        dt_inicio      = sessao["dt_inicio"]
        dt_fim         = dt_inicio + timedelta(minutes=duracao_min)
        potencia_media = sum(r["potencia_kw"] for r in registros) / len(registros)

        demanda_contexto = sessao.get("demanda_no_inicio_kw", 0.0)
        tarifa_kwh, periodo, desconto_label, acrescimo = self.calcular_tarifa(
            hora_inicio, tipo_usuario, demanda_contexto
        )

        custo_energia = energia_total * tarifa_kwh
        desconto      = custo_energia * DESCONTO_ASSINANTE if tipo_usuario == "Assinante" else 0.0
        total         = custo_energia - desconto + TAXA_SERVICO

        co2_evitado   = energia_total * 0.233
        km_estimado   = energia_total * 6

        return {
            "registros":      registros,
            "energia_total":  round(energia_total, 3),
            "duracao_min":    duracao_min,
            "dt_inicio":      dt_inicio,
            "dt_fim":         dt_fim,
            "tarifa_kwh":     tarifa_kwh,
            "periodo":        periodo,
            "acrescimo_kwh":  round(acrescimo, 3),
            "desconto_label": desconto_label,
            "custo_energia":  round(custo_energia, 2),
            "desconto":       round(desconto, 2),
            "taxa_servico":   TAXA_SERVICO,
            "total":          round(total, 2),
            "potencia_media": round(potencia_media, 2),
            "co2_evitado":    round(co2_evitado, 2),
            "km_estimado":    round(km_estimado, 0),
        }
