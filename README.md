# ⚡ ChargeGrid Intelligence — Sistema de Gerenciamento de Recarga

**Disciplina:** Data Structure and Algorithms 

## Integrantes
| NOME | RM |
| ---- | -- |
| LEONARDO SCOTTI TOBIAS | 573305 |
| NATAN SILVA DA COSTA | 573100 |
| ENZO SEIJI DELGADO TABUCHI | 573156 |
| LUCA ALMEIDA LUCARELI | 569061 |
| HENRIQUE ALMEIDA LUCARELI | 569183 |

---

## 📋 Descrição

O **ChargeGrid Intelligence** é um sistema de terminal em Python que simula a operação inteligente de um eletroposto com múltiplos pontos de carregamento simultâneos. Na **Sprint 3**, o sistema evoluiu para uma arquitetura modular baseada no conceito **MVC (Model-View-Controller)** e Padrões de Projeto (**Singleton**, **Facade**). Além do controle dinâmico de potência (Power Management) e tarifação variável, o programa agora gerencia o histórico de sessões utilizando **Classes**, oferecendo funcionalidades nativas de **Busca Sequencial** e **Ordenação (Bubble Sort)**.

---

## ▶️ Como executar

Requisito: 
* Python 3.10+
* Pandas

```bash
python main.py
```
```bash
pip install pandas
```

---

## 🗂️ Estrutura do código (MVC + Design Patterns)

O projeto foi refatorado em múltiplos módulos para garantir coesão e baixo acoplamento:

```text
├── config.py          → Constantes globais (tarifas, limiares, tipos de veículo/usuário).
├── models.py          → Camada Model: Classe Sessao e EstacaoRepository (Singleton).
├── algorithms.py      → Algoritmos estruturais: Busca Sequencial e Bubble Sort.
├── protocols.py       → Mocks de integração: Funções OCPP 1.6 e MODBUS.
├── services.py        → Camada Service (Facade): Regras de negócio (Power Management, tarifas, simulação).
├── ui.py              → Camada View/UI: Formatação de terminal, menus, validação de inputs e relatórios.
└── main.py            → Camada Controller: Laço principal (while True) e orquestração do menu principal.
```

---

## 📐 Padrões de Projeto e Estruturas Utilizadas

| Estrutura/Padrão | Uso no sistema |
|---|---|
| **MVC** | Separação física das responsabilidades (Modelos de dados, Interface e Controle). |
| **Singleton** | A classe `EstacaoRepository` garante uma instância única global para o estado dos pontos e o histórico de recargas. |
| **Facade** | A classe `ServicoRecarga` centraliza e esconde as chamadas complexas de negócio para simplificar a camada de interface. |
| **Classe Orientada a Objetos** | A classe `Sessao` tipifica e encapsula os dados unificados da recarga. |
| **Lista de Objetos** | O histórico agora armazena instâncias de objetos `Sessao` em vez de dicionários. |

---

## 🧠 Algoritmos Implementados (Sprint 3)

### Busca Sequencial `O(n)`
Utilizada na opção do menu "Buscar sessão (Busca Sequencial)". O sistema varre iterativamente a lista de instâncias da classe `Sessao` comparando o ID informado pelo usuário. Em um cenário real, o tempo de busca cresce linearmente conforme a quantidade de sessões cadastradas.

### Bubble Sort `O(n²)`
Utilizado na opção do menu "Ordenar sessões". Permite ordenar in-place o histórico na memória sem o uso da função `.sort()`, dando ao usuário a escolha do critério:
- 1: Por ID
- 2: Por Energia consumida
- 3: Por Custo total da sessão
- 4: Por Tempo de duração (recarga)

---

## ⚙️ Lógica de decisão e controle (Business Rules)

### Power Management (controle de demanda)
| Nível | Demanda total | Potência concedida |
|---|---|---|
| Normal | < 80% (< 35,2 kW) | 100% do solicitado |
| Alerta | 80–95% (35,2–41,8 kW) | 70% do solicitado |
| Crítico | > 95% (> 41,8 kW) | 50% do solicitado |

### Tarifação dinâmica
| Fator | Regra |
|---|---|
| Horário off-peak (0h–5h) | R$ 0,90/kWh |
| Horário normal | R$ 1,20/kWh |
| Horário de ponta (18h–20h) | R$ 1,85/kWh |
| Assinante | Desconto de 15% sobre o custo de energia |
| Frota Corporativa | Teto na tarifa off-peak, independente do horário |
| Alta demanda (> 80%) | Acréscimo de +10% (exceto Frota) |

---

## 🎨 Diferenciais do Projeto

- **Arquitetura Limpa e Escalável** — Modularização avançada dividindo o software em 7 arquivos python especialistas.
- **Implementação Manual de Algoritmos** — Bubble Sort e Sequential Search codificados estruturalmente em Python para fins acadêmicos e analíticos.
- **Análise de Complexidade** — Relatório anexo demonstrando a relação Big-O dos algoritmos desenvolvidos.
- **Estatísticas Computadas** — Cálculo iterativo de ticket médio, faturamento e rastreamento de maiores/menores consumos.
- **Power Management Automático** — Redução preventiva de potência baseada na demanda global do transformador.
- **Telemetria e Protocolos (OCPP/MODBUS)** — Logs detalhados com a estrutura de mensagens oficiais da indústria de mobilidade elétrica.
- **Relatórios em Excel** — Consolidação e exportação massiva das sessões geradas usando a biblioteca `pandas`.
# chargegrid-intelligence
