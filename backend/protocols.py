"""
protocols.py — Mocks das mensagens OCPP 1.6 (Charge Point ↔ Central System).

Na versão API, em vez de imprimir no terminal, cada mensagem vira um EVENTO
guardado no repositório e exibido no painel de telemetria do frontend.
"""

from datetime import datetime


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _evento(acao: str, direcao: str, payload: dict) -> dict:
    return {"timestamp": _agora(), "acao": acao, "direcao": direcao, "payload": payload}


def ocpp_start_transaction(sessao) -> list[dict]:
    tag = f"TAG-{sessao.id:04d}"
    return [
        _evento("Authorize", "CP→CS", {"idTag": tag}),
        _evento("StartTransaction", "CP→CS", {
            "connectorId": sessao.ponto,
            "idTag": tag,
            "meterStart": 0,
            "transactionId": sessao.codigo,
        }),
    ]


def ocpp_stop_transaction(sessao) -> list[dict]:
    return [
        _evento("MeterValues", "CP→CS", {
            "connectorId": sessao.ponto,
            "transactionId": sessao.codigo,
            "SoC": f"{sessao.soc_alvo:.1f}%",
            "Power.Active.Import": f"{sessao.potencia_media_kw:.2f} kW",
        }),
        _evento("StopTransaction", "CP→CS", {
            "transactionId": sessao.codigo,
            "meterStop": f"{sessao.energia_kwh:.3f} kWh",
            "reason": "Local",
        }),
    ]
