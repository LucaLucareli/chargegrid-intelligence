from collections import OrderedDict

CAPACIDADE_TOTAL_KW    = 44.0
NUM_PONTOS             = 4
POTENCIA_MAX_PONTO_KW  = 22.0
POTENCIA_MIN_KW        = 3.7

TARIFA_PADRAO_KWH      = 1.20
TARIFA_PONTA_KWH       = 1.85
TARIFA_OFF_PEAK_KWH    = 0.90
TAXA_SERVICO           = 2.50

DESCONTO_ASSINANTE     = 0.15
ACRESCIMO_ALTA_DEMANDA = 0.10

LIMIAR_REDUCAO_KW      = CAPACIDADE_TOTAL_KW * 0.80
LIMIAR_CRITICO_KW      = CAPACIDADE_TOTAL_KW * 0.95

TIPOS_USUARIO = OrderedDict([
    ("1", "Visitante"),
    ("2", "Assinante"),
    ("3", "Frota Corporativa"),
])

TIPOS_VEICULO = OrderedDict([
    ("1", {"nome": "Hatchback / Sedan",  "bateria_kwh": 40,  "potencia_max": 7.4}),
    ("2", {"nome": "SUV Elétrico",        "bateria_kwh": 77,  "potencia_max": 11.0}),
    ("3", {"nome": "Van / Utilitário",    "bateria_kwh": 90,  "potencia_max": 22.0}),
    ("4", {"nome": "Moto Elétrica",       "bateria_kwh": 5,   "potencia_max": 3.7}),
])
