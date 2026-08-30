from config import NUM_PONTOS

class Sessao:
    def __init__(self, id_sessao, ponto, tipo_usuario, veiculo, carga_inicial, carga_alvo, potencia_solicitada, potencia_alocada, resultado):
        self.id_sessao = id_sessao
        self.ponto = ponto
        self.tipo_usuario = tipo_usuario
        self.veiculo = veiculo
        self.carga_inicial = carga_inicial
        self.carga_alvo = carga_alvo
        self.potencia_solicitada = potencia_solicitada
        self.potencia_alocada_kw = potencia_alocada
        
        # Atributos exigidos pela Sprint 3
        self.id = id_sessao
        self.energia = resultado.get("energia_total", 0.0)
        self.tempo = resultado.get("duracao_min", 0)
        self.custo = resultado.get("total", 0.0)
        
        self.resultado = resultado


class EstacaoRepository:
    """
    Singleton que gerencia o estado global dos pontos de recarga e o histórico.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EstacaoRepository, cls).__new__(cls)
            cls._instance.pontos = {i: None for i in range(1, NUM_PONTOS + 1)}
            cls._instance._prox_id_sessao = 1
            cls._instance.historico_sessoes = []
        return cls._instance

    def obter_ponto(self, ponto: int) -> dict | None:
        return self.pontos.get(ponto)

    def atualizar_ponto(self, ponto: int, sessao_ativa: dict | None):
        self.pontos[ponto] = sessao_ativa

    def adicionar_ao_historico(self, sessao: Sessao):
        self.historico_sessoes.append(sessao)

    def obter_historico(self) -> list:
        return self.historico_sessoes

    def gerar_proximo_id(self) -> int:
        atual = self._prox_id_sessao
        self._prox_id_sessao += 1
        return atual
