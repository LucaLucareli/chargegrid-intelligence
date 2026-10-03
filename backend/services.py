"""
services.py — Camada de Serviço (padrão FACADE).

`ServicoRecarga` é a única porta de entrada das regras de negócio. As rotas
Flask não conhecem o repositório, os algoritmos nem as fórmulas de tarifa:
apenas chamam métodos simples da fachada (iniciar, encerrar, buscar, ordenar...).
"""

from __future__ import annotations

import csv
import io
import math
import random
import time
from datetime import datetime

from algorithms import (
    ALGORITMOS_ORDENACAO, CRITERIOS,
    busca_binaria_por_id, busca_linear_por_cliente, busca_linear_por_id, merge_sort,
)
from config import (
    ACRESCIMO_ALTA_DEMANDA, CAPACIDADE_TOTAL_KW, DESCONTO_ASSINANTE, KG_CO2_POR_KWH,
    KM_POR_KWH, LIMIAR_CRITICO_KW, LIMIAR_REDUCAO_KW, NUM_PONTOS, POTENCIA_MAX_PONTO_KW,
    POTENCIA_MIN_KW, TARIFA_OFF_PEAK_KWH, TARIFA_PADRAO_KWH, TARIFA_PONTA_KWH,
    TAXA_SERVICO, TIPOS_USUARIO, TIPOS_VEICULO,
)
from models import EstacaoRepository, Sessao
from protocols import ocpp_start_transaction, ocpp_stop_transaction


#  Exceções de domínio → convertidas em HTTP pelo app.py
class ErroNegocio(Exception):
    status_http = 400


class ErroValidacao(ErroNegocio):
    status_http = 400


class ErroNaoEncontrado(ErroNegocio):
    status_http = 404


class ErroConflito(ErroNegocio):
    status_http = 409


#  Helpers de validação de entrada (nunca confiar no cliente)
def _numero(dados: dict, campo: str, minimo: float, maximo: float, inteiro: bool = False, padrao=None):
    valor = dados.get(campo, padrao)
    if valor is None or valor == "":
        raise ErroValidacao(f"Campo '{campo}' é obrigatório.")
    if isinstance(valor, bool):                     # bool é subclasse de int em Python
        raise ErroValidacao(f"Campo '{campo}' deve ser numérico.")
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroValidacao(f"Campo '{campo}' deve ser numérico.") from None
    if not math.isfinite(numero):
        raise ErroValidacao(f"Campo '{campo}' inválido.")
    if inteiro:
        if numero != int(numero):
            raise ErroValidacao(f"Campo '{campo}' deve ser inteiro.")
        numero = int(numero)
    if not (minimo <= numero <= maximo):
        raise ErroValidacao(f"Campo '{campo}' deve estar entre {minimo:g} e {maximo:g}.")
    return numero


def _parse_id(valor) -> int:
    """Aceita '7', 7 ou 'CG-0007'."""
    texto = str(valor).strip().upper()
    if texto.startswith("CG-"):
        texto = texto[3:]
    if not texto.isdigit():
        raise ErroValidacao("ID inválido. Use um número (ex.: 7) ou o código (ex.: CG-0007).")
    return int(texto)


def _resumo_sessao(s: Sessao | None) -> dict | None:
    if s is None:
        return None
    return {"id": s.id, "codigo": s.codigo, "cliente": s.cliente,
            "energia_kwh": s.energia_kwh, "custo_total": s.custo_total, "duracao_min": s.duracao_min}


class ServicoRecarga:
    """Facade das operações do eletroposto."""

    def __init__(self, semente: int | None = None):
        self.repo = EstacaoRepository()
        self._rng = random.Random(semente)

    #  Power Management
    def demanda_atual_kw(self) -> float:
        total = 0.0
        for sessao in self.repo.pontos.values():
            if sessao is not None:
                total += sessao.potencia_alocada_kw
        return round(total, 2)

    @staticmethod
    def nivel_demanda(demanda_kw: float) -> tuple[str, float]:
        """Retorna (nível, fator de potência concedida)."""
        if demanda_kw >= LIMIAR_CRITICO_KW:
            return "critico", 0.50
        if demanda_kw >= LIMIAR_REDUCAO_KW:
            return "alerta", 0.70
        return "normal", 1.00

    def calcular_alocacao(self, potencia_solicitada: float) -> tuple[float, float, str, float]:
        demanda = self.demanda_atual_kw()
        nivel, fator = self.nivel_demanda(demanda)
        disponivel = CAPACIDADE_TOTAL_KW - demanda
        if disponivel < POTENCIA_MIN_KW:
            raise ErroConflito(
                f"Capacidade insuficiente: apenas {disponivel:.2f} kW livres "
                f"(mínimo viável {POTENCIA_MIN_KW} kW). Encerre uma sessão ativa."
            )
        alocado = max(potencia_solicitada * fator, POTENCIA_MIN_KW)   # nunca abaixo do mínimo viável
        alocado = min(alocado, disponivel)                           # nunca acima do disponível
        return round(alocado, 2), fator, nivel, demanda

    def painel(self) -> dict:
        demanda = self.demanda_atual_kw()
        nivel, _ = self.nivel_demanda(demanda)
        pontos = []
        for numero, sessao in self.repo.pontos.items():
            pontos.append({
                "ponto": numero,
                "livre": sessao is None,
                "sessao": None if sessao is None else {
                    "id": sessao.id, "codigo": sessao.codigo, "cliente": sessao.cliente,
                    "veiculo": sessao.veiculo, "tipo_usuario": sessao.tipo_usuario,
                    "potencia_alocada_kw": sessao.potencia_alocada_kw,
                    "potencia_solicitada_kw": sessao.potencia_solicitada_kw,
                    "soc_inicial": sessao.soc_inicial, "soc_alvo": sessao.soc_alvo,
                },
            })
        return {
            "capacidade_kw": CAPACIDADE_TOTAL_KW,
            "demanda_kw": demanda,
            "disponivel_kw": round(CAPACIDADE_TOTAL_KW - demanda, 2),
            "uso_pct": round(demanda / CAPACIDADE_TOTAL_KW * 100, 1),
            "nivel": nivel,
            "limiares_kw": {"alerta": LIMIAR_REDUCAO_KW, "critico": LIMIAR_CRITICO_KW},
            "pontos": pontos,
        }

    #  Tarifação dinâmica
    @staticmethod
    def detectar_periodo(hora: int) -> str:
        if 18 <= hora <= 20:
            return "ponta"
        if 0 <= hora <= 5:
            return "off-peak"
        return "normal"

    def calcular_tarifa(self, hora: int, tipo_usuario: str, demanda_kw: float) -> dict:
        periodo = self.detectar_periodo(hora)
        base = {"ponta": TARIFA_PONTA_KWH, "off-peak": TARIFA_OFF_PEAK_KWH, "normal": TARIFA_PADRAO_KWH}[periodo]

        regra = ""
        tarifa = base
        if tipo_usuario == "Frota Corporativa":
            tarifa = base if base < TARIFA_OFF_PEAK_KWH else TARIFA_OFF_PEAK_KWH
            regra = "Frota: tarifa com teto off-peak"
        elif tipo_usuario == "Assinante":
            regra = f"Assinante: {DESCONTO_ASSINANTE * 100:.0f}% de desconto na energia"

        acrescimo = 0.0
        if demanda_kw > LIMIAR_REDUCAO_KW and tipo_usuario != "Frota Corporativa":
            acrescimo = tarifa * ACRESCIMO_ALTA_DEMANDA
            tarifa += acrescimo

        return {"periodo": periodo, "tarifa_base": base, "tarifa_kwh": round(tarifa, 4),
                "acrescimo_kwh": round(acrescimo, 4), "regra_especial": regra}

    def calcular_custo(self, energia_kwh: float, tarifa: dict, tipo_usuario: str) -> dict:
        custo_energia = energia_kwh * tarifa["tarifa_kwh"]
        desconto = custo_energia * DESCONTO_ASSINANTE if tipo_usuario == "Assinante" else 0.0
        return {
            "custo_energia": round(custo_energia, 2),
            "desconto": round(desconto, 2),
            "taxa_servico": TAXA_SERVICO,
            "custo_total": round(custo_energia - desconto + TAXA_SERVICO, 2),
        }

    def tarifacao(self, hora=None, tipo_usuario=None, energia_kwh=None) -> dict:
        """Tabela de tarifas + simulador opcional (GET /api/tarifas?hora=..&tipo_usuario=..)."""
        tabela = {
            "periodos": [
                {"periodo": "off-peak", "faixa": "00h–05h", "tarifa_kwh": TARIFA_OFF_PEAK_KWH},
                {"periodo": "normal", "faixa": "06h–17h · 21h–23h", "tarifa_kwh": TARIFA_PADRAO_KWH},
                {"periodo": "ponta", "faixa": "18h–20h", "tarifa_kwh": TARIFA_PONTA_KWH},
            ],
            "regras": [
                f"Assinante: desconto de {DESCONTO_ASSINANTE * 100:.0f}% sobre o custo de energia",
                "Frota Corporativa: teto na tarifa off-peak em qualquer horário",
                f"Alta demanda (> {LIMIAR_REDUCAO_KW:.1f} kW): +{ACRESCIMO_ALTA_DEMANDA * 100:.0f}% (exceto Frota)",
                f"Taxa de serviço fixa: R$ {TAXA_SERVICO:.2f} por sessão",
            ],
            "periodo_atual": self.detectar_periodo(datetime.now().hour),
        }
        if hora is None and tipo_usuario is None:
            return tabela

        dados = {"hora": hora, "tipo_usuario": tipo_usuario, "energia_kwh": energia_kwh}
        hora = _numero(dados, "hora", 0, 23, inteiro=True)
        energia = _numero(dados, "energia_kwh", 0.1, 500, padrao=20)
        if tipo_usuario not in TIPOS_USUARIO:
            raise ErroValidacao(f"tipo_usuario deve ser um de: {', '.join(TIPOS_USUARIO)}.")
        demanda = self.demanda_atual_kw()
        tarifa = self.calcular_tarifa(hora, tipo_usuario, demanda)
        tabela["simulacao"] = {"hora": hora, "tipo_usuario": tipo_usuario, "energia_kwh": energia,
                               "demanda_atual_kw": demanda, **tarifa,
                               **self.calcular_custo(energia, tarifa, tipo_usuario)}
        return tabela

    #  Simulação física da recarga (minuto a minuto)
    def simular_recarga(self, potencia_kw: float, soc_inicial: float, soc_alvo: float, bateria_kwh: float) -> dict:
        energia_necessaria = (soc_alvo - soc_inicial) / 100 * bateria_kwh
        energia = 0.0
        soma_potencia = 0.0
        minuto = 0
        curva = [[0, round(soc_inicial, 1)]]

        # Passo aproximado para guardar no máximo ~30 pontos da curva de SOC.
        minutos_estimados = max(1, math.ceil(energia_necessaria / (potencia_kw / 60)))
        passo = max(1, minutos_estimados // 30)

        while energia < energia_necessaria:
            variacao = self._rng.uniform(-0.05, 0.05)            # ±5% de oscilação da rede
            potencia = min(max(potencia_kw * (1 + variacao), POTENCIA_MIN_KW), POTENCIA_MAX_PONTO_KW)
            ciclo = min(potencia / 60, energia_necessaria - energia)
            energia += ciclo
            soma_potencia += potencia
            minuto += 1
            if minuto % passo == 0 or energia >= energia_necessaria:
                curva.append([minuto, round(soc_inicial + energia / bateria_kwh * 100, 1)])

        return {"energia_kwh": round(energia, 3), "duracao_min": minuto,
                "potencia_media_kw": round(soma_potencia / minuto, 2) if minuto else 0.0,
                "curva_soc": curva}

    #  CRUD de sessões
    def _validar(self, dados: dict) -> dict:
        if not isinstance(dados, dict):
            raise ErroValidacao("Envie um objeto JSON no corpo da requisição.")

        cliente = str(dados.get("cliente", "")).strip()
        if not (2 <= len(cliente) <= 60):
            raise ErroValidacao("Informe o nome do cliente (2 a 60 caracteres).")

        tipo_usuario = dados.get("tipo_usuario")
        if tipo_usuario not in TIPOS_USUARIO:
            raise ErroValidacao(f"tipo_usuario deve ser um de: {', '.join(TIPOS_USUARIO)}.")

        veiculo_id = dados.get("veiculo_id")
        if veiculo_id not in TIPOS_VEICULO:
            raise ErroValidacao(f"veiculo_id deve ser um de: {', '.join(TIPOS_VEICULO)}.")
        veiculo = TIPOS_VEICULO[veiculo_id]

        soc_inicial = _numero(dados, "soc_inicial", 0, 99)
        soc_alvo = _numero(dados, "soc_alvo", soc_inicial + 1, 100)
        potencia = _numero(dados, "potencia_kw", POTENCIA_MIN_KW, veiculo["potencia_max"],
                           padrao=veiculo["potencia_max"])
        hora = _numero(dados, "hora_inicio", 0, 23, inteiro=True, padrao=datetime.now().hour)

        ponto = dados.get("ponto")
        if ponto in (None, ""):
            ponto = None
        else:
            ponto = _numero(dados, "ponto", 1, NUM_PONTOS, inteiro=True)

        return {"cliente": cliente, "tipo_usuario": tipo_usuario, "veiculo_id": veiculo_id,
                "veiculo": veiculo, "soc_inicial": soc_inicial, "soc_alvo": soc_alvo,
                "potencia_kw": potencia, "hora_inicio": hora, "ponto": ponto,
                "encerrar_agora": bool(dados.get("encerrar_agora", False))}

    def iniciar_sessao(self, dados: dict) -> Sessao:
        """Cadastra uma sessão: valida, reserva o ponto e aplica o Power Management."""
        d = self._validar(dados)
        with self.repo.lock:
            livres = [p for p, s in self.repo.pontos.items() if s is None]
            if not livres:
                raise ErroConflito("Todos os pontos estão ocupados. Encerre uma sessão primeiro.")
            ponto = d["ponto"] if d["ponto"] is not None else livres[0]
            if self.repo.pontos[ponto] is not None:
                raise ErroConflito(f"O ponto #{ponto} está ocupado. Livres: {livres}.")

            alocada, fator, nivel, demanda = self.calcular_alocacao(d["potencia_kw"])

            sessao = Sessao(
                id=self.repo.gerar_proximo_id(), cliente=d["cliente"], ponto=ponto,
                tipo_usuario=d["tipo_usuario"], veiculo_id=d["veiculo_id"],
                veiculo=d["veiculo"]["nome"], bateria_kwh=d["veiculo"]["bateria_kwh"],
                soc_inicial=d["soc_inicial"], soc_alvo=d["soc_alvo"], hora_inicio=d["hora_inicio"],
                potencia_solicitada_kw=d["potencia_kw"], potencia_alocada_kw=alocada,
                fator_reducao=fator, nivel_demanda=nivel, demanda_no_inicio_kw=demanda,
            )
            self.repo.adicionar(sessao)          # append → lista continua ordenada por ID
            self.repo.ocupar_ponto(ponto, sessao)
            for evento in ocpp_start_transaction(sessao):
                self.repo.registrar_evento(evento)

            if d["encerrar_agora"]:
                self.encerrar_sessao(sessao.id)
            return sessao

    def encerrar_sessao(self, id_sessao) -> Sessao:
        """Simula a recarga, calcula a tarifa e libera o ponto."""
        with self.repo.lock:
            sessao, _ = busca_binaria_por_id(self.repo.listar(), _parse_id(id_sessao))
            if sessao is None:
                raise ErroNaoEncontrado(f"Sessão {id_sessao} não encontrada.")
            if sessao.status == "encerrada":
                raise ErroConflito(f"A sessão {sessao.codigo} já foi encerrada.")

            sim = self.simular_recarga(sessao.potencia_alocada_kw, sessao.soc_inicial,
                                       sessao.soc_alvo, sessao.bateria_kwh)
            tarifa = self.calcular_tarifa(sessao.hora_inicio, sessao.tipo_usuario,
                                          sessao.demanda_no_inicio_kw)
            custo = self.calcular_custo(sim["energia_kwh"], tarifa, sessao.tipo_usuario)

            sessao.energia_kwh = sim["energia_kwh"]
            sessao.duracao_min = sim["duracao_min"]
            sessao.potencia_media_kw = sim["potencia_media_kw"]
            sessao.curva_soc = sim["curva_soc"]
            sessao.periodo = tarifa["periodo"]
            sessao.tarifa_kwh = tarifa["tarifa_kwh"]
            sessao.acrescimo_kwh = tarifa["acrescimo_kwh"]
            sessao.regra_especial = tarifa["regra_especial"]
            sessao.custo_energia = custo["custo_energia"]
            sessao.desconto = custo["desconto"]
            sessao.taxa_servico = custo["taxa_servico"]
            sessao.custo_total = custo["custo_total"]
            sessao.co2_evitado_kg = round(sim["energia_kwh"] * KG_CO2_POR_KWH, 2)
            sessao.km_estimado = round(sim["energia_kwh"] * KM_POR_KWH, 0)
            sessao.status = "encerrada"
            sessao.encerrado_em = datetime.now().isoformat(timespec="seconds")

            self.repo.liberar_ponto(sessao.ponto)
            for evento in ocpp_stop_transaction(sessao):
                self.repo.registrar_evento(evento)
            return sessao

    def listar(self, status: str | None = None) -> list[Sessao]:
        if status in (None, "", "todas"):
            return list(self.repo.listar())
        if status not in ("ativa", "encerrada"):
            raise ErroValidacao("status deve ser 'ativa', 'encerrada' ou 'todas'.")
        resultado = []
        for s in self.repo.listar():
            if s.status == status:
                resultado.append(s)
        return resultado

    def _encerradas(self) -> list[Sessao]:
        return self.listar("encerrada")

    #  BUSCA
    def buscar(self, chave: str, valor: str, algoritmo: str = "binaria") -> dict:
        if not valor or not str(valor).strip():
            raise ErroValidacao("Informe o valor a ser buscado.")
        sessoes = self.repo.listar()
        inicio = time.perf_counter()

        if chave == "id":
            id_alvo = _parse_id(valor)
            if algoritmo == "binaria":
                achada, met = busca_binaria_por_id(sessoes, id_alvo)
                info = ("Busca Binária", "O(log n)")
            elif algoritmo == "linear":
                achada, met = busca_linear_por_id(sessoes, id_alvo)
                info = ("Busca Linear", "O(n)")
            else:
                raise ErroValidacao("algoritmo deve ser 'binaria' ou 'linear'.")
            resultados = [] if achada is None else [achada]
        elif chave == "cliente":
            # Busca binária exigiria a lista ordenada por nome; como a lista global
            # é ordenada por ID, a busca por nome é necessariamente LINEAR.
            resultados, met = busca_linear_por_cliente(sessoes, str(valor).strip())
            info = ("Busca Linear (substring)", "O(n)")
        else:
            raise ErroValidacao("chave deve ser 'id' ou 'cliente'.")

        return {
            "chave": chave, "valor": valor, "algoritmo": info[0], "complexidade": info[1],
            "tamanho_lista": len(sessoes), "comparacoes": met["comparacoes"],
            "tempo_ms": round((time.perf_counter() - inicio) * 1000, 4),
            "encontrados": len(resultados), "resultados": [s.to_dict() for s in resultados],
        }

    #  ORDENAÇÃO
    def ordenar(self, criterio: str = "id", ordem: str = "asc", algoritmo: str = "merge") -> dict:
        if criterio not in CRITERIOS:
            raise ErroValidacao(f"criterio deve ser um de: {', '.join(CRITERIOS)}.")
        if ordem not in ("asc", "desc"):
            raise ErroValidacao("ordem deve ser 'asc' ou 'desc'.")
        if algoritmo not in ALGORITMOS_ORDENACAO:
            raise ErroValidacao(f"algoritmo deve ser um de: {', '.join(ALGORITMOS_ORDENACAO)}.")

        estrategia = ALGORITMOS_ORDENACAO[algoritmo]
        sessoes = self.repo.listar()
        n = len(sessoes)

        inicio = time.perf_counter()
        ordenadas, metricas = estrategia["fn"](sessoes, criterio, ordem == "desc")
        tempo_ms = (time.perf_counter() - inicio) * 1000

        return {
            "criterio": criterio, "ordem": ordem, "algoritmo": estrategia["nome"],
            "complexidade": estrategia["complexidade"], "n": n,
            "metricas": {**metricas, "tempo_ms": round(tempo_ms, 4)},
            "referencia_teorica": {
                "n_log2_n": round(n * math.log2(n), 1) if n > 1 else 0,
                "n_quadrado": n * n,
            },
            "sessoes": [s.to_dict() for s in ordenadas],
        }

    #  ESTATÍSTICAS (laços manuais — sem sum()/max()/min() com key)
    def estatisticas(self) -> dict:
        encerradas = self._encerradas()
        qtd = len(encerradas)
        energia_total = faturamento = co2 = km = minutos = 0.0
        maior = menor = mais_cara = None
        por_usuario: dict[str, dict] = {t: {"sessoes": 0, "receita": 0.0, "energia_kwh": 0.0} for t in TIPOS_USUARIO}
        por_periodo: dict[str, dict] = {p: {"sessoes": 0, "receita": 0.0} for p in ("off-peak", "normal", "ponta")}
        por_veiculo: dict[str, int] = {}

        for s in encerradas:                                  # uma única passada: O(n)
            energia_total += s.energia_kwh
            faturamento += s.custo_total
            co2 += s.co2_evitado_kg
            km += s.km_estimado
            minutos += s.duracao_min
            if maior is None or s.energia_kwh > maior.energia_kwh:
                maior = s
            if menor is None or s.energia_kwh < menor.energia_kwh:
                menor = s
            if mais_cara is None or s.custo_total > mais_cara.custo_total:
                mais_cara = s
            por_usuario[s.tipo_usuario]["sessoes"] += 1
            por_usuario[s.tipo_usuario]["receita"] += s.custo_total
            por_usuario[s.tipo_usuario]["energia_kwh"] += s.energia_kwh
            por_periodo[s.periodo]["sessoes"] += 1
            por_periodo[s.periodo]["receita"] += s.custo_total
            por_veiculo[s.veiculo] = por_veiculo.get(s.veiculo, 0) + 1

        # Mediana do custo: exige a lista ordenada → reutiliza o nosso Merge Sort.
        mediana = 0.0
        if qtd:
            ordenadas, _ = merge_sort(encerradas, "custo")
            meio = qtd // 2
            mediana = ordenadas[meio].custo_total if qtd % 2 else (ordenadas[meio - 1].custo_total + ordenadas[meio].custo_total) / 2

        for grupo in (por_usuario, por_periodo):
            for item in grupo.values():
                for k in item:
                    if isinstance(item[k], float):
                        item[k] = round(item[k], 2)

        return {
            "total_sessoes": len(self.repo.listar()),
            "sessoes_ativas": len(self.repo.listar()) - qtd,
            "sessoes_encerradas": qtd,
            "energia_total_kwh": round(energia_total, 2),
            "faturamento_total": round(faturamento, 2),
            "ticket_medio": round(faturamento / qtd, 2) if qtd else 0.0,
            "mediana_custo": round(mediana, 2),
            "energia_media_kwh": round(energia_total / qtd, 2) if qtd else 0.0,
            "duracao_media_min": round(minutos / qtd, 1) if qtd else 0.0,
            "preco_medio_kwh": round(faturamento / energia_total, 2) if energia_total else 0.0,
            "co2_evitado_kg": round(co2, 2),
            "km_gerados": round(km, 0),
            "maior_consumo": _resumo_sessao(maior),
            "menor_consumo": _resumo_sessao(menor),
            "sessao_mais_cara": _resumo_sessao(mais_cara),
            "por_tipo_usuario": por_usuario,
            "por_periodo": por_periodo,
            "por_veiculo": por_veiculo,
        }

    #  RESUMO FINAL
    def resumo(self) -> dict:
        encerradas = self._encerradas()
        stats = self.estatisticas()

        top, _ = merge_sort(encerradas, "custo", decrescente=True)

        # Ranking de clientes: agrega por nome (dict → O(1) por acesso) e ordena
        # a lista agregada com o MESMO Merge Sort (chave passada como função).
        agregado: dict[str, dict] = {}
        for s in encerradas:
            c = agregado.setdefault(s.cliente, {"cliente": s.cliente, "sessoes": 0, "energia_kwh": 0.0, "gasto": 0.0})
            c["sessoes"] += 1
            c["energia_kwh"] = round(c["energia_kwh"] + s.energia_kwh, 3)
            c["gasto"] = round(c["gasto"] + s.custo_total, 2)
        ranking, _ = merge_sort(list(agregado.values()), lambda c: c["gasto"], decrescente=True)

        return {
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "estacao": {"capacidade_kw": CAPACIDADE_TOTAL_KW, "pontos": NUM_PONTOS},
            "indicadores": stats,
            "top_sessoes": [s.to_dict() for s in top[:5]],
            "ranking_clientes": ranking[:5],
            "sessoes_ativas": [s.to_dict() for s in self.listar("ativa")],
            "algoritmos": [
                {"operacao": "Ordenação principal", "algoritmo": "Merge Sort", "complexidade": "O(n log n)"},
                {"operacao": "Ordenação comparativa", "algoritmo": "Bubble Sort", "complexidade": "O(n²)"},
                {"operacao": "Busca por ID", "algoritmo": "Busca Binária", "complexidade": "O(log n)"},
                {"operacao": "Busca por cliente", "algoritmo": "Busca Linear", "complexidade": "O(n)"},
                {"operacao": "Cadastro", "algoritmo": "append na lista", "complexidade": "O(1) amortizado"},
            ],
        }

    def exportar_csv(self) -> str:
        buffer = io.StringIO()
        campos = ["codigo", "cliente", "status", "ponto", "tipo_usuario", "veiculo", "soc_inicial", "soc_alvo",
                  "hora_inicio", "potencia_solicitada_kw", "potencia_alocada_kw", "nivel_demanda",
                  "energia_kwh", "duracao_min", "periodo", "tarifa_kwh", "custo_energia", "desconto",
                  "taxa_servico", "custo_total", "co2_evitado_kg", "km_estimado", "criado_em", "encerrado_em"]
        writer = csv.DictWriter(buffer, fieldnames=campos, extrasaction="ignore", delimiter=";")
        writer.writeheader()
        for s in self.repo.listar():
            writer.writerow(s.to_dict())
        return buffer.getvalue()

    #  Cenário de demonstração (para o vídeo)
    def executar_demo(self) -> dict:
        with self.repo.lock:
            if any(s is not None for s in self.repo.pontos.values()):
                raise ErroConflito("Encerre as sessões ativas antes de rodar o cenário de demonstração.")

            def lote(itens, encerrar=True):
                criadas = [self.iniciar_sessao(item) for item in itens]
                if encerrar:
                    for s in criadas:
                        self.encerrar_sessao(s.id)
                return criadas

            # Lote 1 — horário de PONTA com 4 carros simultâneos: dispara o Power
            # Management (alerta a partir de 35,2 kW) e o acréscimo de alta demanda.
            lote([
                {"cliente": "Transportadora Alfa", "tipo_usuario": "Frota Corporativa", "veiculo_id": "van", "soc_inicial": 30, "soc_alvo": 95, "potencia_kw": 22, "hora_inicio": 19},
                {"cliente": "Ana Souza", "tipo_usuario": "Assinante", "veiculo_id": "suv", "soc_inicial": 20, "soc_alvo": 80, "potencia_kw": 11, "hora_inicio": 19},
                {"cliente": "Bruno Lima", "tipo_usuario": "Visitante", "veiculo_id": "moto", "soc_inicial": 15, "soc_alvo": 100, "potencia_kw": 3.7, "hora_inicio": 19},
                {"cliente": "Carla Mendes", "tipo_usuario": "Visitante", "veiculo_id": "hatch", "soc_inicial": 10, "soc_alvo": 90, "potencia_kw": 7.4, "hora_inicio": 19},
            ])
            # Lote 2 — madrugada (off-peak) e horário normal. A van chega por último
            # e recebe apenas a potência que sobrou no transformador (limite físico).
            lote([
                {"cliente": "Diego Rocha", "tipo_usuario": "Assinante", "veiculo_id": "hatch", "soc_inicial": 5, "soc_alvo": 100, "potencia_kw": 7.4, "hora_inicio": 3},
                {"cliente": "Ana Souza", "tipo_usuario": "Assinante", "veiculo_id": "suv", "soc_inicial": 40, "soc_alvo": 70, "potencia_kw": 11, "hora_inicio": 10},
                {"cliente": "Elisa Prado", "tipo_usuario": "Visitante", "veiculo_id": "suv", "soc_inicial": 25, "soc_alvo": 60, "potencia_kw": 11, "hora_inicio": 15},
                {"cliente": "Transportadora Alfa", "tipo_usuario": "Frota Corporativa", "veiculo_id": "van", "soc_inicial": 50, "soc_alvo": 80, "potencia_kw": 22, "hora_inicio": 13},
            ])
            # Lote 3 — duas sessões ficam ATIVAS para demonstrar o painel.
            lote([
                {"cliente": "Felipe Costa", "tipo_usuario": "Visitante", "veiculo_id": "suv", "soc_inicial": 12, "soc_alvo": 85, "potencia_kw": 11, "ponto": 1},
                {"cliente": "Gabriela Nunes", "tipo_usuario": "Assinante", "veiculo_id": "hatch", "soc_inicial": 33, "soc_alvo": 90, "potencia_kw": 7.4, "ponto": 3},
            ], encerrar=False)

            return {"mensagem": "Cenário de demonstração criado.", "total_sessoes": len(self.repo.listar())}

    def resetar(self) -> None:
        with self.repo.lock:
            self.repo.limpar()

    def eventos(self) -> list[dict]:
        return list(self.repo.eventos)
