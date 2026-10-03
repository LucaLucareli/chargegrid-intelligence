"""
==================================================================
   ChargeGrid Intelligence — API REST (Flask)
==================================================================

Camada CONTROLLER da arquitetura MVC:
  • recebe a requisição HTTP (JSON / query string),
  • delega para a Facade `ServicoRecarga` (regras de negócio + algoritmos),
  • devolve JSON para o frontend.

Padrões usados aqui:
  • Application Factory → `create_app()` cria a aplicação (facilita testes).
  • Blueprint           → todas as rotas da API agrupadas sob o prefixo /api.
  • Tratamento central de erros → exceções de domínio viram HTTP 400/404/409.

Executar:
    pip install -r requirements.txt
    python backend/app.py          →  http://127.0.0.1:5000

┌────────┬──────────────────────────────────┬────────────────────────────────────────┐
│ Método │ Rota                             │ Ação                                   │
├────────┼──────────────────────────────────┼────────────────────────────────────────┤
│ GET    │ /api/health                      │ status da API                          │
│ GET    │ /api/config                      │ catálogos (usuários, veículos, pontos) │
│ GET    │ /api/estacao                     │ painel: demanda, pontos, nível         │
│ POST   │ /api/sessoes                     │ CADASTRAR sessão                       │
│ GET    │ /api/sessoes?status=             │ LISTAR todas                           │
│ GET    │ /api/sessoes/<id>                │ BUSCAR por ID                          │
│ GET    │ /api/sessoes/busca?chave=&valor= │ BUSCAR                                 │
│ POST   │ /api/sessoes/<id>/encerrar       │ encerrar sessão (simula + tarifa)      │
│ GET    │ /api/sessoes/ordenar?criterio=   │ ORDENAR                                │
│ GET    │ /api/estatisticas                │ ESTATÍSTICAS                           │
│ GET    │ /api/tarifas?hora=&tipo_usuario= │ TARIFAÇÃO (tabela + simulador)         │
│ GET    │ /api/resumo                      │ RESUMO FINAL                           │
│ GET    │ /api/resumo/csv                  │ exporta o histórico em CSV             │
│ GET    │ /api/eventos                     │ log de telemetria OCPP                 │
│ POST   │ /api/demo                        │ popula um cenário de demonstração      │
│ POST   │ /api/reset                       │ limpa a memória                        │
└────────┴──────────────────────────────────┴────────────────────────────────────────┘
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from flask import Blueprint, Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from config import CAPACIDADE_TOTAL_KW, NUM_PONTOS, POTENCIA_MIN_KW, TIPOS_USUARIO, TIPOS_VEICULO
from services import ErroNegocio, ErroNaoEncontrado, ServicoRecarga, _parse_id

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

api = Blueprint("api", __name__, url_prefix="/api")
servico = ServicoRecarga()          # Facade única (usa o Repository Singleton)


# ── Rotas utilitárias ────────────────────────────────────────────────────────
@api.get("/health")
def health():
    return jsonify(status="ok", horario=datetime.now().isoformat(timespec="seconds"))


@api.get("/config")
def config():
    return jsonify(
        tipos_usuario=list(TIPOS_USUARIO),
        veiculos=TIPOS_VEICULO,
        num_pontos=NUM_PONTOS,
        capacidade_kw=CAPACIDADE_TOTAL_KW,
        potencia_min_kw=POTENCIA_MIN_KW,
    )


@api.get("/estacao")
def estacao():
    return jsonify(servico.painel())


# ── Sessões ──────────────────────────────────────────────────────────────────
@api.post("/sessoes")
def cadastrar_sessao():
    dados = request.get_json(silent=True)
    sessao = servico.iniciar_sessao(dados)
    return jsonify(sessao.to_dict()), 201


@api.get("/sessoes")
def listar_sessoes():
    sessoes = servico.listar(request.args.get("status"))
    return jsonify(total=len(sessoes), sessoes=[s.to_dict() for s in sessoes])


# o Flask já prioriza segmentos literais sobre variáveis.
@api.get("/sessoes/busca")
def buscar_sessao():
    a = request.args
    return jsonify(servico.buscar(a.get("chave", "id"), a.get("valor", ""), a.get("algoritmo", "binaria")))


@api.get("/sessoes/ordenar")
def ordenar_sessoes():
    a = request.args
    return jsonify(servico.ordenar(a.get("criterio", "id"), a.get("ordem", "asc"), a.get("algoritmo", "merge")))


@api.get("/sessoes/<id_sessao>")
def obter_sessao(id_sessao: str):
    resultado = servico.buscar("id", id_sessao, "binaria")
    if not resultado["encontrados"]:
        raise ErroNaoEncontrado(f"Sessão {id_sessao} não encontrada.")
    return jsonify(resultado["resultados"][0])


@api.post("/sessoes/<id_sessao>/encerrar")
def encerrar_sessao(id_sessao: str):
    return jsonify(servico.encerrar_sessao(_parse_id(id_sessao)).to_dict())


# ── Indicadores ──────────────────────────────────────────────────────────────
@api.get("/estatisticas")
def estatisticas():
    return jsonify(servico.estatisticas())


@api.get("/tarifas")
def tarifas():
    a = request.args
    return jsonify(servico.tarifacao(a.get("hora"), a.get("tipo_usuario"), a.get("energia_kwh")))


@api.get("/resumo")
def resumo():
    return jsonify(servico.resumo())


@api.get("/resumo/csv")
def resumo_csv():
    nome = f"chargegrid_{datetime.now():%Y%m%d_%H%M%S}.csv"
    # BOM UTF-8 para o Excel abrir os acentos corretamente.
    return Response("\ufeff" + servico.exportar_csv(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={nome}"})


@api.get("/eventos")
def eventos():
    return jsonify(servico.eventos())


# ── Utilidades de demonstração ───────────────────────────────────────────────
@api.post("/demo")
def demo():
    return jsonify(servico.executar_demo()), 201


@api.post("/reset")
def reset():
    servico.resetar()
    return jsonify(mensagem="Memória reiniciada.")


#  Application Factory
def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.json.ensure_ascii = False          # acentos legíveis no JSON
    app.json.sort_keys = False             # mantém a ordem dos campos

    # CORS apenas nas rotas /api — permite abrir o index.html via Live Server/arquivo.
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.register_blueprint(api)

    # Serve o frontend pelo próprio Flask (um único comando sobe tudo).
    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:arquivo>")
    def estaticos(arquivo: str):
        return send_from_directory(FRONTEND_DIR, arquivo)   # protege contra path traversal

    # ── Tratamento centralizado de erros → sempre JSON ──
    @app.errorhandler(ErroNegocio)
    def erro_negocio(e: ErroNegocio):
        return jsonify(erro=str(e)), e.status_http

    @app.errorhandler(HTTPException)
    def erro_http(e: HTTPException):
        return jsonify(erro=e.description), e.code

    @app.errorhandler(Exception)
    def erro_inesperado(e: Exception):
        app.logger.exception("Erro não tratado")
        return jsonify(erro="Erro interno no servidor."), 500

    return app


app = create_app()

if __name__ == "__main__":
    # debug desligado por padrão: o debugger do Werkzeug permite execução remota de código.
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG") == "1")
