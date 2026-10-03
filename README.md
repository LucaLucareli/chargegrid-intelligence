# ⚡ ChargeGrid Intelligence — Sistema de Gerenciamento de Recarga

**Disciplina:** Data Structure and Algorithms · **Sprint 4 — Demonstração e Defesa Técnica**

## Integrantes
| NOME | RM |
| ---- | -- |
| LEONARDO SCOTTI TOBIAS | 573305 |
| NATAN SILVA DA COSTA | 573100 |
| ENZO SEIJI DELGADO TABUCHI | 573156 |
| LUCA ALMEIDA LUCARELI | 569061 |
| HENRIQUE ALMEIDA LUCARELI | 569183 |

---

## Descrição

Simulação de um eletroposto com 4 pontos de recarga (44 kW). Na Sprint 4 o sistema virou uma aplicação web:

- **Backend:** API REST em **Flask** com as regras de negócio (Power Management, tarifa dinâmica), a lista de sessões em memória e os algoritmos de **busca** (Binária e Linear) e **ordenação** (Merge Sort e Bubble Sort), todos escritos do zero.
- **Frontend:** HTML + CSS + JavaScript puro, que chama a API com `fetch()`.

## ▶️ Como executar

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python backend/app.py
```

Depois abra **http://127.0.0.1:5000** (o Flask serve o frontend). Para ter dados na hora, clique em **"Cenário demo"**.

Testes: `python backend/tests/test_app.py -v`

> ⚠️ A API não tem autenticação e escuta apenas em `127.0.0.1`. Serve para demonstração acadêmica e não deve ser exposta na internet.

## Estrutura

```text
backend/
├── app.py         → Controller: Flask (Application Factory + Blueprint /api), tratamento de erros
├── services.py    → Facade ServicoRecarga: regras de negócio, estatísticas, resumo
├── algorithms.py  → Merge Sort, Bubble Sort, Busca Binária, Busca Linear (do zero)
├── models.py      → dataclass Sessao + lista global HISTORICO_SESSOES + Repository Singleton
├── protocols.py   → mensagens OCPP 1.6 simuladas (viram eventos de telemetria)
├── config.py      → constantes (tarifas, limiares, veículos)
└── tests/         → 15 testes unittest (algoritmos + API)
frontend/
├── index.html · style.css · script.js
```

## Rotas da API

| Método | Rota | Ação |
|---|---|---|
| POST | `/api/sessoes` | Cadastrar sessão |
| GET | `/api/sessoes?status=` | Listar todas |
| GET | `/api/sessoes/<id>` | Buscar por ID (binária) |
| GET | `/api/sessoes/busca?chave=id\|cliente&valor=&algoritmo=binaria\|linear` | Buscar |
| POST | `/api/sessoes/<id>/encerrar` | Encerrar (simula a recarga e calcula a tarifa) |
| GET | `/api/sessoes/ordenar?criterio=id\|cliente\|energia\|custo\|tempo&ordem=asc\|desc&algoritmo=merge\|bubble` | Ordenar |
| GET | `/api/estatisticas` | Estatísticas |
| GET | `/api/tarifas?hora=&tipo_usuario=&energia_kwh=` | Tabela de tarifas e simulador |
| GET | `/api/resumo` · `/api/resumo/csv` | Resumo final · exportar CSV |
| GET | `/api/estacao` · `/api/eventos` · `/api/config` | Painel, telemetria OCPP, catálogos |
| POST | `/api/demo` · `/api/reset` | Cenário de demonstração · limpar memória |

## Padrões de projeto

| Camada | Padrão | Onde |
|---|---|---|
| Backend | MVC | `models` / `services` / `app` + frontend como View |
| Backend | Singleton | `EstacaoRepository` (estado único e thread-safe) |
| Backend | Facade | `ServicoRecarga` |
| Backend | Strategy | `CRITERIOS` (chaves de ordenação) e `ALGORITMOS_ORDENACAO` |
| Backend | Application Factory + Blueprint | `create_app()` e `api` |
| Frontend | Gateway/Facade | `ApiClient` (todo `fetch` passa por ele) |
| Frontend | Observer | `Store` (componentes assinam o estado) |
| Frontend | Singleton | `Toast`, `Modal` |
| Frontend | Strategy | Views escolhidas pelo `Router` |

## Algoritmos e complexidade

| Operação | Algoritmo | Tempo | Espaço |
|---|---|---|---|
| Ordenar (principal) | Merge Sort (estável) | O(n log n) em todos os casos | O(n) |
| Ordenar (comparativo) | Bubble Sort com parada antecipada | O(n²) · melhor caso O(n) | O(1) |
| Buscar por ID | Busca Binária | O(log n) | O(1) |
| Buscar por cliente | Busca Linear (substring) | O(n) | O(k) resultados |
| Cadastrar | `append` | O(1) amortizado | — |

A interface mostra, a cada busca ou ordenação, o número real de comparações ao lado dos valores teóricos n·log₂n e n².
