from datetime import datetime

def _ocpp_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

def _ocpp_log(direcao: str, mensagem: dict):
    seta = "→ CP→CS" if direcao == "envio" else "← CS→CP"
    print(f"\n  [OCPP] {seta}  {_ocpp_timestamp()}")
    for k, v in mensagem.items():
        print(f"         {k:<22}: {v}")

def ocpp_boot_notification(ponto: int):
    _ocpp_log("envio", {
        "action":           "BootNotification",
        "chargePointModel": "ChargeGrid-P22AC",
        "chargePointVendor":"ChargeGrid Intelligence",
        "connectorId":      ponto,
        "firmwareVersion":  "v2.1.4",
    })
    _ocpp_log("recebimento", {
        "status":      "Accepted",
        "currentTime": _ocpp_timestamp(),
        "interval":    30,
    })

def ocpp_start_transaction(id_sessao: str, ponto: int, dados: dict):
    _ocpp_log("envio", {
        "action": "Authorize",
        "idTag":  f"TAG-{id_sessao[-4:]}",
    })
    _ocpp_log("recebimento", {
        "idTagInfo.status": "Accepted",
    })
    _ocpp_log("envio", {
        "action":        "StartTransaction",
        "connectorId":   ponto,
        "idTag":         f"TAG-{id_sessao[-4:]}",
        "meterStart":    0,
        "timestamp":     _ocpp_timestamp(),
        "transactionId": id_sessao,
    })
    _ocpp_log("recebimento", {
        "transactionId":    id_sessao,
        "idTagInfo.status": "Accepted",
    })

def ocpp_meter_values(id_sessao: str, ponto: int, soc: float, energia_kwh: float, potencia_kw: float):
    _ocpp_log("envio", {
        "action":        "MeterValues",
        "connectorId":   ponto,
        "transactionId": id_sessao,
        "SoC [%]":       f"{soc:.1f}",
        "Energy.Active.Import.Register [kWh]": f"{energia_kwh:.3f}",
        "Power.Active.Import [kW]":            f"{potencia_kw:.2f}",
        "timestamp":     _ocpp_timestamp(),
    })

def ocpp_stop_transaction(sessao: dict, resultado: dict):
    _ocpp_log("envio", {
        "action":          "StopTransaction",
        "transactionId":   sessao["id_sessao"],
        "meterStop [kWh]": f"{resultado['energia_total']:.3f}",
        "timestamp":       _ocpp_timestamp(),
        "reason":          "Local",
    })
    _ocpp_log("recebimento", {
        "idTagInfo.status": "Accepted",
    })

def modbus_leitura_medidor(ponto: int, potencia_kw: float, energia_kwh: float):
    registrador = 0x1000 + ponto * 0x10
    print(f"\n  [MODBUS] Leitura — Registrador 0x{registrador:04X}  Ponto #{ponto}")
    print(f"           Tensão         : 220.0 V")
    print(f"           Corrente       : {(potencia_kw * 1000 / 220):.1f} A")
    print(f"           Potência Ativa : {potencia_kw:.2f} kW")
    print(f"           Energia Acum.  : {energia_kwh:.3f} kWh")
    print(f"           FP             : 0.97")
