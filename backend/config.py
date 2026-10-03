"""
config.py — Constantes globais do ChargeGrid Intelligence.

Centralizar os parâmetros aqui evita "números mágicos" espalhados pelo código
e permite ajustar regras de negócio (tarifas, limiares) em um único lugar.
"""

# ── Infraestrutura do eletroposto ───────────────────────────────────────────
CAPACIDADE_TOTAL_KW   = 44.0   # capacidade do transformador
NUM_PONTOS            = 4      # quantidade de conectores
POTENCIA_MAX_PONTO_KW = 22.0   # limite físico de cada conector (AC trifásico)
POTENCIA_MIN_KW       = 3.7    # abaixo disso a recarga não é viável

# ── Tarifação (R$/kWh) ───────────────────────────────────────────────────────
TARIFA_PADRAO_KWH   = 1.20
TARIFA_PONTA_KWH    = 1.85
TARIFA_OFF_PEAK_KWH = 0.90
TAXA_SERVICO        = 2.50     # valor fixo por sessão

DESCONTO_ASSINANTE     = 0.15  # 15% sobre o custo de energia
ACRESCIMO_ALTA_DEMANDA = 0.10  # +10% na tarifa quando demanda > 80%

# ── Power Management ─────────────────────────────────────────────────────────
LIMIAR_REDUCAO_KW = CAPACIDADE_TOTAL_KW * 0.80   # 35,2 kW → nível ALERTA
LIMIAR_CRITICO_KW = CAPACIDADE_TOTAL_KW * 0.95   # 41,8 kW → nível CRÍTICO

# ── Fatores de impacto ambiental ─────────────────────────────────────────────
KG_CO2_POR_KWH = 0.233   # emissão evitada vs. motor a combustão
KM_POR_KWH     = 6.0     # autonomia média de um VE

# ── Catálogos (usados na validação da API e nos <select> do frontend) ───────
TIPOS_USUARIO = ("Visitante", "Assinante", "Frota Corporativa")

TIPOS_VEICULO = {
    "hatch": {"nome": "Hatchback / Sedan", "bateria_kwh": 40, "potencia_max": 7.4},
    "suv":   {"nome": "SUV Elétrico",      "bateria_kwh": 77, "potencia_max": 11.0},
    "van":   {"nome": "Van / Utilitário",  "bateria_kwh": 90, "potencia_max": 22.0},
    "moto":  {"nome": "Moto Elétrica",     "bateria_kwh": 5,  "potencia_max": 3.7},
}
