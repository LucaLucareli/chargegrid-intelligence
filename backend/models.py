"""
models.py — Camada Model: estrutura de dados da Sessão e repositório em memória.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime

from config import NUM_PONTOS


@dataclass(slots=True)
class Sessao:
    """Representa UMA sessão de recarga de veículo elétrico."""

    # ── Identificação ──
    id: int                      # chave primária sequencial
    cliente: str                 # nome do cliente
    ponto: int                   # conector utilizado (1..NUM_PONTOS)
    tipo_usuario: str            # Visitante | Assinante | Frota Corporativa
    veiculo_id: str
    veiculo: str
    bateria_kwh: float

    # ── Parâmetros de entrada ──
    soc_inicial: float
    soc_alvo: float
    hora_inicio: int
    potencia_solicitada_kw: float

    # ── Power Management (definido no início) ──
    potencia_alocada_kw: float
    fator_reducao: float
    nivel_demanda: str           # normal | alerta | critico
    demanda_no_inicio_kw: float

    status: str = "ativa"        # ativa | encerrada
    criado_em: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    # ── Resultado (preenchido ao encerrar) ──
    encerrado_em: str | None = None
    energia_kwh: float = 0.0
    duracao_min: int = 0
    potencia_media_kw: float = 0.0
    periodo: str = ""            # normal | ponta | off-peak
    tarifa_kwh: float = 0.0
    acrescimo_kwh: float = 0.0
    regra_especial: str = ""
    custo_energia: float = 0.0
    desconto: float = 0.0
    taxa_servico: float = 0.0
    custo_total: float = 0.0
    co2_evitado_kg: float = 0.0
    km_estimado: float = 0.0
    curva_soc: list = field(default_factory=list)   # amostras [minuto, soc] p/ gráfico

    @property
    def codigo(self) -> str:
        """Identificador amigável exibido na interface (ex.: CG-0007)."""
        return f"CG-{self.id:04d}"

    def to_dict(self) -> dict:
        """Serializa para JSON (resposta da API)."""
        dados = asdict(self)
        dados["codigo"] = self.codigo
        return dados


# ── "Banco de dados" em memória ─────────────────────────────────────────────
# Lista global única com TODAS as sessões (ativas e encerradas).
HISTORICO_SESSOES: list[Sessao] = []


class EstacaoRepository:
    """
    Singleton: existe apenas UMA instância, compartilhada por toda a API.
    Guarda a lista de sessões, o estado dos pontos e o log de eventos OCPP.
    """

    _instance: EstacaoRepository | None = None
    _init_lock = threading.Lock()

    def __new__(cls):
        # Double-checked locking: seguro mesmo com o servidor Flask multi-thread.
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst.sessoes = HISTORICO_SESSOES
                    inst.pontos = {}
                    inst.eventos = deque(maxlen=60)
                    inst.lock = threading.RLock()
                    inst._prox_id = 1
                    inst._resetar_pontos()
                    cls._instance = inst
        return cls._instance

    # ── Sessões ──
    def adicionar(self, sessao: Sessao) -> None:
        self.sessoes.append(sessao)

    def listar(self) -> list[Sessao]:
        return self.sessoes

    def gerar_proximo_id(self) -> int:
        atual = self._prox_id
        self._prox_id += 1
        return atual

    # ── Pontos de recarga ──
    def _resetar_pontos(self) -> None:
        self.pontos = {p: None for p in range(1, NUM_PONTOS + 1)}

    def ocupar_ponto(self, ponto: int, sessao: Sessao) -> None:
        self.pontos[ponto] = sessao

    def liberar_ponto(self, ponto: int) -> None:
        self.pontos[ponto] = None

    # ── Eventos (telemetria OCPP) ──
    def registrar_evento(self, evento: dict) -> None:
        self.eventos.appendleft(evento)      # mais recente primeiro

    def limpar(self) -> None:
        """Reinicia o estado (usado no botão 'Resetar' e nos testes)."""
        self.sessoes.clear()                 # mantém a MESMA lista global
        self.eventos.clear()
        self._resetar_pontos()
        self._prox_id = 1
