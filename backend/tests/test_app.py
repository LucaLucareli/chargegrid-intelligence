"""
Testes automatizados (unittest — biblioteca padrão).
Executar a partir da raiz:  python backend/tests/test_app.py -v
"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms import (  # noqa: E402
    bubble_sort, busca_binaria_por_id, busca_linear_por_cliente, busca_linear_por_id, merge_sort,
)
from app import create_app  # noqa: E402
from models import EstacaoRepository, HISTORICO_SESSOES, Sessao  # noqa: E402


def fake(i, custo=0.0, cliente="Cliente", energia=0.0, tempo=0):
    return Sessao(id=i, cliente=cliente, ponto=1, tipo_usuario="Visitante", veiculo_id="hatch", veiculo="Hatch",
                  bateria_kwh=40, soc_inicial=10, soc_alvo=90, hora_inicio=10, potencia_solicitada_kw=7.4,
                  potencia_alocada_kw=7.4, fator_reducao=1.0, nivel_demanda="normal", demanda_no_inicio_kw=0,
                  custo_total=custo, energia_kwh=energia, duracao_min=tempo)


class TestOrdenacao(unittest.TestCase):
    def setUp(self):
        rng = random.Random(42)
        self.lista = [fake(i, custo=round(rng.uniform(0, 100), 2), energia=rng.uniform(0, 60),
                           tempo=rng.randint(10, 500), cliente=rng.choice(["bia", "Ana", "carlos", "Davi"]))
                      for i in range(1, 60)]

    def _esperado(self, chave, desc=False):
        return [s.id for s in sorted(self.lista, key=chave, reverse=desc)]

    def test_merge_e_bubble_todos_criterios(self):
        chaves = {"id": lambda s: s.id, "custo": lambda s: s.custo_total, "energia": lambda s: s.energia_kwh,
                  "tempo": lambda s: s.duracao_min, "cliente": lambda s: s.cliente.casefold()}
        for fn in (merge_sort, bubble_sort):
            for criterio, chave in chaves.items():
                for desc in (False, True):
                    with self.subTest(fn=fn.__name__, criterio=criterio, desc=desc):
                        ordenada, _ = fn(self.lista, criterio, desc)
                        valores = [chave(s) for s in ordenada]
                        esperado = [chave(s) for s in sorted(self.lista, key=chave, reverse=desc)]
                        self.assertEqual(valores, esperado)

    def test_estabilidade(self):
        lista = [fake(1, custo=5), fake(2, custo=1), fake(3, custo=5), fake(4, custo=1)]
        for fn in (merge_sort, bubble_sort):
            ordenada, _ = fn(lista, "custo")
            self.assertEqual([s.id for s in ordenada], [2, 4, 1, 3])

    def test_nao_altera_lista_original(self):
        ids = [s.id for s in self.lista]
        merge_sort(self.lista, "custo", True)
        bubble_sort(self.lista, "custo", True)
        self.assertEqual([s.id for s in self.lista], ids)

    def test_bubble_melhor_caso_linear(self):
        _, m = bubble_sort(self.lista, "id")
        self.assertEqual(m["comparacoes"], len(self.lista) - 1)
        self.assertEqual(m["trocas"], 0)

    def test_listas_vazias_e_unitarias(self):
        for fn in (merge_sort, bubble_sort):
            self.assertEqual(fn([], "id")[0], [])
            self.assertEqual(len(fn([fake(1)], "id")[0]), 1)


class TestBusca(unittest.TestCase):
    def setUp(self):
        self.lista = [fake(i, cliente=f"Cliente {i}") for i in range(1, 1025)]

    def test_binaria_encontra_todos_e_limite_log(self):
        for alvo in (1, 512, 1024, 333):
            s, m = busca_binaria_por_id(self.lista, alvo)
            self.assertEqual(s.id, alvo)
            self.assertLessEqual(m["comparacoes"], 11)

    def test_binaria_nao_encontra(self):
        for alvo in (0, 1025, -3):
            s, m = busca_binaria_por_id(self.lista, alvo)
            self.assertIsNone(s)
            self.assertEqual(m["indice"], -1)
        self.assertIsNone(busca_binaria_por_id([], 1)[0])

    def test_linear_para_ao_encontrar(self):
        s, m = busca_linear_por_id(self.lista, 10)
        self.assertEqual((s.id, m["comparacoes"]), (10, 10))
        s, m = busca_linear_por_id(self.lista, 9999)
        self.assertIsNone(s)
        self.assertEqual(m["comparacoes"], 1024)

    def test_linear_cliente_parcial_case_insensitive(self):
        achados, m = busca_linear_por_cliente(self.lista, "cliente 10")
        self.assertEqual([s.id for s in achados], [10, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109] + list(range(1000, 1025)))
        self.assertEqual(m["comparacoes"], 1024)


class TestAPI(unittest.TestCase):
    def setUp(self):
        EstacaoRepository().limpar()
        self.c = create_app().test_client()

    def novo(self, **extra):
        dados = {"cliente": "Teste", "tipo_usuario": "Visitante", "veiculo_id": "hatch",
                 "soc_inicial": 20, "soc_alvo": 80, "potencia_kw": 7.4, "hora_inicio": 10, **extra}
        return self.c.post("/api/sessoes", json=dados)

    def test_fluxo_completo(self):
        r = self.novo()
        self.assertEqual(r.status_code, 201)
        sid = r.get_json()["id"]
        self.assertEqual(len(HISTORICO_SESSOES), 1)
        self.assertEqual(self.c.get("/api/estacao").get_json()["demanda_kw"], 7.4)

        r = self.c.post(f"/api/sessoes/{sid}/encerrar")
        s = r.get_json()
        self.assertEqual(s["status"], "encerrada")
        self.assertAlmostEqual(s["energia_kwh"], 24.0, places=2)
        self.assertAlmostEqual(s["custo_total"], round(24 * 1.2 + 2.5, 2), places=2)
        self.assertEqual(self.c.post(f"/api/sessoes/{sid}/encerrar").status_code, 409)

        self.assertEqual(self.c.get("/api/sessoes").get_json()["total"], 1)
        self.assertEqual(self.c.get("/api/sessoes/CG-0001").get_json()["id"], 1)
        self.assertEqual(self.c.get("/api/sessoes/99").status_code, 404)
        self.assertEqual(self.c.get("/api/estatisticas").get_json()["sessoes_encerradas"], 1)
        self.assertIn("ranking_clientes", self.c.get("/api/resumo").get_json())
        self.assertIn("CG-0001", self.c.get("/api/resumo/csv").get_data(as_text=True))

    def test_regras_tarifa(self):
        a = self.novo(tipo_usuario="Assinante", hora_inicio=19, encerrar_agora=True).get_json()
        self.assertEqual(a["tarifa_kwh"], 1.85)
        self.assertAlmostEqual(a["desconto"], round(a["custo_energia"] * 0.15, 2), places=2)
        f = self.novo(tipo_usuario="Frota Corporativa", hora_inicio=19, encerrar_agora=True).get_json()
        self.assertEqual(f["tarifa_kwh"], 0.9)

    def test_power_management_e_capacidade(self):
        self.novo(veiculo_id="van", potencia_kw=22)
        self.novo(veiculo_id="suv", potencia_kw=11)
        self.novo(veiculo_id="moto", potencia_kw=3.7)
        s = self.novo(veiculo_id="hatch", potencia_kw=7.4).get_json()
        self.assertEqual(s["nivel_demanda"], "alerta")
        self.assertAlmostEqual(s["potencia_alocada_kw"], 5.18)
        self.assertEqual(self.novo().status_code, 409)

    def test_validacoes(self):
        casos = [{"cliente": ""}, {"tipo_usuario": "Hacker"}, {"veiculo_id": "tanque"}, {"soc_alvo": 10},
                 {"potencia_kw": 50}, {"hora_inicio": 25}, {"soc_inicial": "abc"}, {"ponto": 9}, {"soc_inicial": True}]
        for extra in casos:
            with self.subTest(extra=extra):
                r = self.novo(**extra)
                self.assertEqual(r.status_code, 400)
                self.assertIn("erro", r.get_json())
        self.assertEqual(self.c.post("/api/sessoes", data="x").status_code, 400)

    def test_rotas_busca_ordenacao(self):
        self.assertEqual(self.c.post("/api/demo").status_code, 201)
        r = self.c.get("/api/sessoes/ordenar?criterio=custo&ordem=desc&algoritmo=merge").get_json()
        custos = [s["custo_total"] for s in r["sessoes"]]
        self.assertEqual(custos, sorted(custos, reverse=True))
        self.assertEqual(r["algoritmo"], "Merge Sort")
        self.assertEqual(self.c.get("/api/sessoes/ordenar?criterio=xyz").status_code, 400)

        r = self.c.get("/api/sessoes/busca?chave=cliente&valor=ana").get_json()
        self.assertTrue(r["encontrados"] >= 1)
        r = self.c.get("/api/sessoes/busca?chave=id&valor=5&algoritmo=linear").get_json()
        self.assertEqual((r["encontrados"], r["comparacoes"]), (1, 5))
        self.assertEqual(self.c.get("/api/sessoes/busca?chave=id&valor=abc").status_code, 400)
        self.assertEqual(self.c.post("/api/demo").status_code, 409)

    def test_tarifas_e_frontend(self):
        r = self.c.get("/api/tarifas?hora=3&tipo_usuario=Visitante&energia_kwh=10").get_json()
        self.assertEqual(r["simulacao"]["tarifa_kwh"], 0.9)
        self.assertEqual(self.c.get("/api/tarifas?hora=3&tipo_usuario=X").status_code, 400)
        r = self.c.get("/"); self.assertEqual(r.status_code, 200); r.close()
        r = self.c.get("/script.js"); self.assertEqual(r.status_code, 200); r.close()
        self.assertEqual(self.c.get("/../backend/app.py").status_code, 404)


if __name__ == "__main__":
    unittest.main()
