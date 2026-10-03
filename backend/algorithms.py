"""
algorithms.py — Algoritmos de BUSCA e ORDENAÇÃO.
"""

from __future__ import annotations

from typing import Callable

from models import Sessao

#  STRATEGY — critérios de ordenação disponíveis
CRITERIOS: dict[str, Callable[[Sessao], object]] = {
    "id":      lambda s: s.id,
    "cliente": lambda s: s.cliente.casefold(),   # ordem alfabética sem diferenciar maiúsculas
    "energia": lambda s: s.energia_kwh,
    "custo":   lambda s: s.custo_total,
    "tempo":   lambda s: s.duracao_min,
}


def _criar_comparador(criterio: str | Callable, decrescente: bool) -> Callable[[object, object], bool]:
    chave = criterio if callable(criterio) else CRITERIOS[criterio]
    if decrescente:
        return lambda a, b: chave(a) >= chave(b)
    return lambda a, b: chave(a) <= chave(b)


#  ORDENAÇÃO 1 — MERGE SORT
def merge_sort(sessoes: list, criterio: str | Callable = "id", decrescente: bool = False) -> tuple[list[Sessao], dict]:
    """
    Ordena as sessões com Merge Sort (Dividir e Conquistar).
    """
    vem_antes = _criar_comparador(criterio, decrescente)
    metricas = {"comparacoes": 0, "escritas": 0}

    def _ordenar(lista: list[Sessao]) -> list[Sessao]:
        if len(lista) <= 1:
            return lista

        meio = len(lista) // 2
        esquerda = _ordenar(lista[:meio])
        direita = _ordenar(lista[meio:])

        resultado: list[Sessao] = []
        i = j = 0
        while i < len(esquerda) and j < len(direita):
            metricas["comparacoes"] += 1
            if vem_antes(esquerda[i], direita[j]):
                resultado.append(esquerda[i])
                i += 1
            else:
                resultado.append(direita[j])
                j += 1
            metricas["escritas"] += 1

        while i < len(esquerda):
            resultado.append(esquerda[i])
            i += 1
            metricas["escritas"] += 1
        while j < len(direita):
            resultado.append(direita[j])
            j += 1
            metricas["escritas"] += 1

        return resultado

    return _ordenar(list(sessoes)), metricas


#  ORDENAÇÃO 2 — BUBBLE SORT
def bubble_sort(sessoes: list, criterio: str | Callable = "id", decrescente: bool = False) -> tuple[list[Sessao], dict]:
    """
    Bubble Sort com parada antecipada.
    """
    vem_antes = _criar_comparador(criterio, decrescente)
    lista = list(sessoes)
    n = len(lista)
    metricas = {"comparacoes": 0, "trocas": 0, "passadas": 0}

    for i in range(n - 1):
        metricas["passadas"] += 1
        trocou = False

        for j in range(n - 1 - i):
            metricas["comparacoes"] += 1

            if not vem_antes(lista[j], lista[j + 1]):
                lista[j], lista[j + 1] = lista[j + 1], lista[j]
                metricas["trocas"] += 1
                trocou = True

        if not trocou:
            break

    return lista, metricas


#  BUSCA 1 — BUSCA LINEAR (sequencial)
def busca_linear_por_id(sessoes: list[Sessao], id_procurado: int) -> tuple[Sessao | None, dict]:
    """
    Percorre a lista do início ao fim comparando o ID de cada sessão.
    """
    comparacoes = 0
    for i in range(len(sessoes)):
        comparacoes += 1
        if sessoes[i].id == id_procurado:
            return sessoes[i], {"comparacoes": comparacoes, "indice": i}
    return None, {"comparacoes": comparacoes, "indice": -1}


def busca_linear_por_cliente(sessoes: list[Sessao], termo: str) -> tuple[list[Sessao], dict]:
    """
    Busca textual parcial e sem diferenciar maiúsculas (ex.: "ana" acha "Ana Souza").
    """
    termo = termo.casefold()
    encontrados: list[Sessao] = []
    comparacoes = 0
    for sessao in sessoes:
        comparacoes += 1
        if termo in sessao.cliente.casefold():
            encontrados.append(sessao)
    return encontrados, {"comparacoes": comparacoes}


#  BUSCA 2 — BUSCA BINÁRIA por ID
def busca_binaria_por_id(sessoes: list[Sessao], id_procurado: int) -> tuple[Sessao | None, dict]:
    """
    A cada passo compara com o elemento do MEIO e descarta metade do intervalo.
    """
    inicio, fim = 0, len(sessoes) - 1
    comparacoes = 0

    while inicio <= fim:
        meio = (inicio + fim) // 2
        comparacoes += 1
        id_meio = sessoes[meio].id

        if id_meio == id_procurado:
            return sessoes[meio], {"comparacoes": comparacoes, "indice": meio}
        if id_meio < id_procurado:
            inicio = meio + 1
        else:
            fim = meio - 1

    return None, {"comparacoes": comparacoes, "indice": -1}


# Registro de algoritmos (Strategy) usado pela camada de serviço.
ALGORITMOS_ORDENACAO = {
    "merge":  {"fn": merge_sort,  "nome": "Merge Sort",  "complexidade": "O(n log n)"},
    "bubble": {"fn": bubble_sort, "nome": "Bubble Sort", "complexidade": "O(n²)"},
}
