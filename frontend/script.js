/* ══════════════════════════════════════════════════════════════════════════
   ChargeGrid Intelligence — Frontend (JavaScript puro, ES2020+)

   Padrões de projeto aplicados:
   • Gateway / Facade  → ApiClient: único ponto de acesso HTTP (fetch) à API Flask.
   • Observer          → Store: estado central; componentes "assinam" mudanças.
   • Singleton         → Toast e Modal: uma única instância na página.
   • Strategy          → Views: cada tela implementa a mesma interface (enter/render)
                         e o Router escolhe a estratégia em tempo de execução.
   • Template (views)  → funções puras que recebem dados e devolvem HTML.
   ══════════════════════════════════════════════════════════════════════════ */
"use strict";

(() => {
  /* ────────────────────────────────────────────────────────────────────────
     1. CONFIGURAÇÃO
     Se a página for servida pelo Flask, usa a mesma origem; se for aberta
     como arquivo ou via Live Server, aponta para o Flask local.
     ──────────────────────────────────────────────────────────────────────── */
  const API_BASE =
    window.CHARGEGRID_API ??
    (location.protocol === "file:" || ["5500", "5501", "3000", "8080"].includes(location.port)
      ? "http://127.0.0.1:5000"
      : "");
  const POLLING_MS = 4000;

  /* ────────────────────────────────────────────────────────────────────────
     2. UTILITÁRIOS
     ──────────────────────────────────────────────────────────────────────── */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  /** Escapa texto antes de inserir no HTML (evita XSS com o nome do cliente). */
  const esc = (v) =>
    String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const num = (v, d = 1) => Number(v ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
  const fmt = {
    brl: (v) => brl.format(v ?? 0),
    kwh: (v) => `${num(v, 2)} kWh`,
    kw: (v) => `${num(v, 1)} kW`,
    pct: (v) => `${num(v, 0)}%`,
    min: (m) => (m >= 60 ? `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}min` : `${m ?? 0} min`),
    hora: (h) => `${String(h).padStart(2, "0")}:00`,
    data: (iso) => (iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—"),
  };

  const debounce = (fn, ms = 300) => {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  };

  const EMOJI_VEICULO = { hatch: "🚗", suv: "🚙", van: "🚐", moto: "🛵" };
  const NIVEL = {
    normal: { label: "Normal", cls: "badge--ok", cor: "var(--primary)" },
    alerta: { label: "Alerta", cls: "badge--warn", cor: "var(--warn)" },
    critico: { label: "Crítico", cls: "badge--crit", cor: "var(--crit)" },
  };
  const PERIODO = {
    "off-peak": { label: "Off-peak", cls: "badge--violet" },
    normal: { label: "Normal", cls: "badge--info" },
    ponta: { label: "Ponta", cls: "badge--crit" },
  };
  const ICON = {
    bolt: '<svg viewBox="0 0 24 24"><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/></svg>',
    money: '<svg viewBox="0 0 24 24"><path d="M12 1a11 11 0 1 0 0 22 11 11 0 0 0 0-22zm1 17.9V21h-2v-2.1c-1.7-.3-3-1.3-3.2-3h2c.2.9 1 1.5 2.3 1.5 1.4 0 2-.7 2-1.4 0-.8-.6-1.3-2.4-1.7-2-.5-3.4-1.3-3.4-3.1 0-1.5 1.2-2.6 2.8-2.9V6h2v2.3c1.6.4 2.6 1.6 2.7 3h-2c-.1-.9-.7-1.5-1.8-1.5-1.2 0-1.8.6-1.8 1.3 0 .7.7 1.1 2.3 1.5 1.9.5 3.5 1.2 3.5 3.2 0 1.6-1.2 2.7-3 3z"/></svg>',
    list: '<svg viewBox="0 0 24 24"><path d="M3 5h18v2H3V5zm0 6h18v2H3v-2zm0 6h18v2H3v-2z"/></svg>',
    leaf: '<svg viewBox="0 0 24 24"><path d="M17 8C8 10 5.9 16.2 3.8 21.3l1.9.7 1-2.3c.5.2 1 .3 1.3.3C19 20 22 3 22 3c-1 2-8 2.3-13 3.3S2 11.5 2 13.5 3.8 17.3 3.8 17.3C7 8 17 8 17 8z"/></svg>',
    clock: '<svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 11h-5v-2h3V6h2v7z"/></svg>',
    plug: '<svg viewBox="0 0 24 24"><path d="M16 7V3h-2v4h-4V3H8v4H6v6l3.5 3.5V21h5v-4.5L18 13V7h-2z"/></svg>',
    car: '<svg viewBox="0 0 24 24"><path d="M18.9 6a1.5 1.5 0 0 0-1.4-1h-11A1.5 1.5 0 0 0 5.1 6L3 12v8a1 1 0 0 0 1 1h1a1 1 0 0 0 1-1v-1h12v1a1 1 0 0 0 1 1h1a1 1 0 0 0 1-1v-8l-2.1-6zM6.5 16a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm11 0a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zM5 11l1.5-4.5h11L19 11H5z"/></svg>',
    search: '<svg viewBox="0 0 24 24"><path d="M15.5 14h-.8l-.3-.3A6.5 6.5 0 1 0 14 15.5l.3.3v.8l5 5 1.5-1.5-5-5zm-6 0a4.5 4.5 0 1 1 0-9 4.5 4.5 0 0 1 0 9z"/></svg>',
  };

  /* ────────────────────────────────────────────────────────────────────────
     3. GATEWAY / FACADE — ApiClient
     Esconde os detalhes do fetch (URL, headers, JSON, erros HTTP).
     ──────────────────────────────────────────────────────────────────────── */
  class ApiError extends Error {
    constructor(message, status) { super(message); this.status = status; }
  }

  class ApiClient {
    constructor(base) { this.base = base; }

    async request(path, { method = "GET", body, params } = {}) {
      const url = new URL(`${this.base}/api${path}`, location.href);
      if (params) {
        Object.entries(params).forEach(([k, v]) => v !== undefined && v !== "" && url.searchParams.set(k, v));
      }
      let resp;
      try {
        resp = await fetch(url, {
          method,
          headers: body ? { "Content-Type": "application/json" } : undefined,
          body: body ? JSON.stringify(body) : undefined,
        });
      } catch {
        throw new ApiError("Não foi possível conectar à API Flask. Ela está rodando?", 0);
      }
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new ApiError(data.erro || `Erro HTTP ${resp.status}`, resp.status);
      return data;
    }

    health() { return this.request("/health"); }
    config() { return this.request("/config"); }
    estacao() { return this.request("/estacao"); }
    eventos() { return this.request("/eventos"); }
    listar(status) { return this.request("/sessoes", { params: { status } }); }
    obter(id) { return this.request(`/sessoes/${encodeURIComponent(id)}`); }
    cadastrar(dados) { return this.request("/sessoes", { method: "POST", body: dados }); }
    encerrar(id) { return this.request(`/sessoes/${encodeURIComponent(id)}/encerrar`, { method: "POST" }); }
    buscar(chave, valor, algoritmo) { return this.request("/sessoes/busca", { params: { chave, valor, algoritmo } }); }
    ordenar(criterio, ordem, algoritmo) { return this.request("/sessoes/ordenar", { params: { criterio, ordem, algoritmo } }); }
    estatisticas() { return this.request("/estatisticas"); }
    tarifas(params) { return this.request("/tarifas", { params }); }
    resumo() { return this.request("/resumo"); }
    demo() { return this.request("/demo", { method: "POST" }); }
    reset() { return this.request("/reset", { method: "POST" }); }
    csvUrl() { return new URL(`${this.base}/api/resumo/csv`, location.href).href; }
  }

  /* ────────────────────────────────────────────────────────────────────────
     4. OBSERVER — Store
     Estado único da aplicação. `set()` notifica apenas quem assinou a chave.
     ──────────────────────────────────────────────────────────────────────── */
  class Store {
    #state;
    #listeners = new Map();

    constructor(initial) { this.#state = { ...initial }; }

    get(key) { return this.#state[key]; }

    set(partial) {
      this.#state = { ...this.#state, ...partial };
      Object.keys(partial).forEach((k) => (this.#listeners.get(k) || []).forEach((fn) => fn(this.#state[k], this.#state)));
    }

    subscribe(key, fn) {
      if (!this.#listeners.has(key)) this.#listeners.set(key, []);
      this.#listeners.get(key).push(fn);
    }
  }

  /* ────────────────────────────────────────────────────────────────────────
     5. SINGLETONS DE UI — Toast e Modal
     ──────────────────────────────────────────────────────────────────────── */
  const Toast = (() => {
    let instance;
    const create = () => {
      const root = $("#toasts");
      const show = (title, msg = "", type = "success", ms = 4200) => {
        const el = document.createElement("div");
        el.className = `toast toast--${type}`;
        el.innerHTML = `<div>${type === "error" ? "⚠️" : type === "warn" ? "⚡" : "✅"}</div>
          <div><strong>${esc(title)}</strong>${msg ? `<span>${esc(msg)}</span>` : ""}</div>`;
        root.appendChild(el);
        setTimeout(() => { el.classList.add("is-leaving"); el.addEventListener("animationend", () => el.remove()); }, ms);
      };
      return {
        success: (t, m) => show(t, m, "success"),
        warn: (t, m) => show(t, m, "warn"),
        error: (t, m) => show(t, m, "error", 6000),
      };
    };
    return { get: () => (instance ??= create()) };
  })();

  const Modal = (() => {
    let instance;
    const create = () => {
      const root = $("#modal");
      const body = $("#modalBody");
      let lastFocus = null;
      const close = () => { root.hidden = true; lastFocus?.focus(); };
      root.addEventListener("click", (e) => e.target.closest("[data-close]") && close());
      document.addEventListener("keydown", (e) => e.key === "Escape" && !root.hidden && close());
      return {
        open(html) {
          lastFocus = document.activeElement;
          body.innerHTML = html;
          root.hidden = false;
          $(".modal__close", root).focus();
        },
        close,
      };
    };
    return { get: () => (instance ??= create()) };
  })();

  /* ────────────────────────────────────────────────────────────────────────
     6. COMPONENTES (templates puros: dados → HTML)
     ──────────────────────────────────────────────────────────────────────── */
  const Components = {
    kpi({ label, value, hint = "", icon = ICON.bolt, accent = "var(--primary)" }) {
      return `<article class="kpi" style="--accent:${accent}">
        <div class="kpi__icon" aria-hidden="true">${icon}</div>
        <div class="kpi__label">${esc(label)}</div>
        <div class="kpi__value">${esc(value)}</div>
        ${hint ? `<div class="kpi__hint">${esc(hint)}</div>` : ""}
      </article>`;
    },

    gauge(estacao) {
      const r = 80, circ = 2 * Math.PI * r, arc = circ * 0.75;
      const pct = Math.min(estacao.uso_pct / 100, 1);
      const cor = NIVEL[estacao.nivel].cor;
      return `<svg viewBox="0 0 200 200" role="img" aria-label="Uso de ${estacao.uso_pct}% da capacidade">
        <circle class="gauge__track" cx="100" cy="100" r="${r}" stroke-dasharray="${arc} ${circ}" transform="rotate(135 100 100)"/>
        <circle class="gauge__bar" cx="100" cy="100" r="${r}" stroke="${cor}"
          stroke-dasharray="${arc} ${circ}" stroke-dashoffset="${arc * (1 - pct)}" transform="rotate(135 100 100)"
          style="filter: drop-shadow(0 0 8px ${cor})"/>
        <text class="gauge__value" x="100" y="100" text-anchor="middle">${num(estacao.uso_pct, 0)}%</text>
        <text class="gauge__sub" x="100" y="122" text-anchor="middle">${num(estacao.demanda_kw, 1)} / ${num(estacao.capacidade_kw, 0)} kW</text>
        <text class="gauge__sub" x="100" y="160" text-anchor="middle">${num(estacao.disponivel_kw, 1)} kW livres</text>
      </svg>`;
    },

    point(p) {
      if (p.livre) {
        return `<div class="point">
          <div class="point__head"><span class="point__num">Ponto #${p.ponto}</span><span class="badge">Livre</span></div>
          <div class="point__empty">${ICON.plug}Disponível</div>
          <button class="btn btn--ghost btn--sm" data-goto="nova" data-ponto="${p.ponto}">Usar este ponto</button>
        </div>`;
      }
      const s = p.sessao;
      const reduzido = s.potencia_alocada_kw < s.potencia_solicitada_kw;
      return `<div class="point is-busy">
        <div class="point__head"><span class="point__num">Ponto #${p.ponto}</span><span class="badge badge--ok">Carregando</span></div>
        <div>
          <div class="point__client">${esc(s.cliente)}</div>
          <div class="point__meta">${esc(s.codigo)} · ${esc(s.veiculo)}</div>
        </div>
        <div class="charge-bar" aria-hidden="true"><span style="width:${s.soc_alvo}%; left:0; opacity:.25"></span><span style="width:${s.soc_inicial}%"></span></div>
        <div class="point__meta">${fmt.pct(s.soc_inicial)} → ${fmt.pct(s.soc_alvo)} ·
          <strong style="color:${reduzido ? "var(--warn)" : "var(--primary)"}">${fmt.kw(s.potencia_alocada_kw)}</strong>
          ${reduzido ? `<span title="Power Management reduziu a potência"> (pedido ${fmt.kw(s.potencia_solicitada_kw)})</span>` : ""}
        </div>
        <button class="btn btn--primary btn--sm" data-encerrar="${s.id}">Encerrar sessão</button>
      </div>`;
    },

    event(e) {
      const payload = Object.entries(e.payload).map(([k, v]) => `${k}=${v}`).join("  ");
      return `<li class="event event--${esc(e.acao)}">
        <time>${esc(e.timestamp.slice(11))}</time><strong>${esc(e.direcao)} ${esc(e.acao)}</strong><code title="${esc(payload)}">${esc(payload)}</code>
      </li>`;
    },

    statusBadge: (status) =>
      status === "ativa" ? '<span class="badge badge--ok">● Ativa</span>' : '<span class="badge">Encerrada</span>',

    row(s) {
      const ativa = s.status === "ativa";
      return `<tr data-id="${s.id}" tabindex="0" aria-label="Ver detalhes da sessão ${esc(s.codigo)}">
        <td class="num">${esc(s.codigo)}</td>
        <td class="client">${esc(s.cliente)}<small>${esc(s.tipo_usuario)}</small></td>
        <td>${EMOJI_VEICULO[s.veiculo_id] ?? ""} ${esc(s.veiculo)}</td>
        <td class="num">#${s.ponto}</td>
        <td class="num">${fmt.kw(s.potencia_alocada_kw)}</td>
        <td class="num">${ativa ? "—" : fmt.kwh(s.energia_kwh)}</td>
        <td class="num">${ativa ? "—" : fmt.min(s.duracao_min)}</td>
        <td class="num">${ativa ? "—" : fmt.brl(s.custo_total)}</td>
        <td>${Components.statusBadge(s.status)}</td>
        <td><div class="row-actions">${ativa ? `<button class="btn btn--primary btn--sm" data-encerrar="${s.id}">Encerrar</button>` : ""}</div></td>
      </tr>`;
    },

    empty(msg, icon = ICON.list) {
      return `<div class="empty">${icon}<p>${esc(msg)}</p></div>`;
    },

    bars(items, { valueFmt = (v) => v, colors = [] } = {}) {
      let max = 0;
      items.forEach((i) => { if (i.value > max) max = i.value; });
      if (!items.length || max === 0) return Components.empty("Sem dados ainda. Encerre algumas sessões.");
      return items.map((i, idx) => `<div>
        <div class="bar__head"><span>${esc(i.label)}</span><span>${esc(valueFmt(i.value))}</span></div>
        <div class="bar__track"><div class="bar__fill" data-w="${(i.value / max) * 100}" style="--c:${colors[idx] ?? "var(--grad)"}"></div></div>
      </div>`).join("");
    },

    sparkline(curva) {
      if (!curva?.length || curva.length < 2) return "";
      const W = 600, H = 150, P = 24;
      const maxX = curva[curva.length - 1][0] || 1;
      const x = (m) => P + (m / maxX) * (W - 2 * P);
      const y = (soc) => H - P - (soc / 100) * (H - 2 * P);
      const pts = curva.map(([m, s]) => `${x(m).toFixed(1)},${y(s).toFixed(1)}`).join(" ");
      return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Curva de carga (SOC ao longo do tempo)">
        <defs><linearGradient id="sparkGrad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stop-color="#22e3a4" stop-opacity=".45"/><stop offset="1" stop-color="#22e3a4" stop-opacity="0"/></linearGradient></defs>
        <polygon class="area" points="${x(0)},${H - P} ${pts} ${x(maxX)},${H - P}"/>
        <polyline class="line" points="${pts}"/>
        <text x="${P}" y="${H - 6}">0 min</text><text x="${W - P}" y="${H - 6}" text-anchor="end">${maxX} min</text>
        <text x="${P}" y="14">SOC 100%</text>
      </svg>`;
    },

    detalhe(s) {
      const ativa = s.status === "ativa";
      const nivel = NIVEL[s.nivel_demanda];
      const periodo = PERIODO[s.periodo];
      return `
        <h2 id="modalTitle" style="font-size:1.3rem">${esc(s.codigo)} · ${esc(s.cliente)}</h2>
        <p class="muted">${Components.statusBadge(s.status)} <span class="badge ${nivel.cls}">Demanda ${nivel.label}</span>
          ${periodo ? `<span class="badge ${periodo.cls}">${periodo.label}</span>` : ""}</p>
        <div class="detail-grid">
          <div><small>Veículo</small><strong>${EMOJI_VEICULO[s.veiculo_id] ?? ""} ${esc(s.veiculo)}</strong></div>
          <div><small>Usuário</small><strong>${esc(s.tipo_usuario)}</strong></div>
          <div><small>Ponto</small><strong>#${s.ponto}</strong></div>
          <div><small>SOC</small><strong>${fmt.pct(s.soc_inicial)} → ${fmt.pct(s.soc_alvo)}</strong></div>
          <div><small>Potência pedida</small><strong>${fmt.kw(s.potencia_solicitada_kw)}</strong></div>
          <div><small>Potência alocada</small><strong>${fmt.kw(s.potencia_alocada_kw)} (${num(s.fator_reducao * 100, 0)}%)</strong></div>
          <div><small>Hora de início</small><strong>${fmt.hora(s.hora_inicio)}</strong></div>
          <div><small>Demanda no início</small><strong>${fmt.kw(s.demanda_no_inicio_kw)}</strong></div>
          ${ativa ? "" : `
          <div><small>Energia</small><strong>${fmt.kwh(s.energia_kwh)}</strong></div>
          <div><small>Duração</small><strong>${fmt.min(s.duracao_min)}</strong></div>
          <div><small>CO₂ evitado</small><strong>${num(s.co2_evitado_kg, 2)} kg</strong></div>
          <div><small>Autonomia</small><strong>~${num(s.km_estimado, 0)} km</strong></div>`}
        </div>
        ${ativa
          ? `<p class="note">Sessão em andamento. Ao encerrar, o backend simula a recarga minuto a minuto e calcula a tarifa.</p>
             <button class="btn btn--primary btn--lg" data-encerrar="${s.id}">Encerrar e calcular cobrança</button>`
          : `<h3 style="margin-top:1rem">Curva de carga</h3>${Components.sparkline(s.curva_soc)}
             <h3 style="margin:1rem 0 .5rem">Cobrança</h3>
             <ul class="receipt">
               <li><span>Tarifa aplicada</span><span class="mono">${fmt.brl(s.tarifa_kwh)}/kWh${s.acrescimo_kwh > 0 ? " (+10% demanda)" : ""}</span></li>
               <li><span>Energia (${fmt.kwh(s.energia_kwh)})</span><span class="mono">${fmt.brl(s.custo_energia)}</span></li>
               ${s.desconto > 0 ? `<li><span>Desconto assinante</span><span class="mono">− ${fmt.brl(s.desconto)}</span></li>` : ""}
               <li><span>Taxa de serviço</span><span class="mono">${fmt.brl(s.taxa_servico)}</span></li>
               <li class="total"><span>Total</span><span class="mono">${fmt.brl(s.custo_total)}</span></li>
             </ul>
             ${s.regra_especial ? `<p class="note">Regra aplicada: ${esc(s.regra_especial)}</p>` : ""}`}`;
    },
  };

  /* ────────────────────────────────────────────────────────────────────────
     7. APLICAÇÃO — instâncias e ações (Commands)
     ──────────────────────────────────────────────────────────────────────── */
  const api = new ApiClient(API_BASE);
  const store = new Store({
    online: null, config: null, estacao: null, eventos: [], stats: null,
    tabela: { modo: "lista", sessoes: [], meta: null }, filtroStatus: "todas",
  });

  /** Envolve uma ação assíncrona com spinner no botão e toast de erro. */
  async function withFeedback(btn, fn) {
    btn?.classList.add("is-loading");
    if (btn) btn.disabled = true;
    try { return await fn(); }
    catch (err) { Toast.get().error("Ops!", err.message); if (err.status === 0) store.set({ online: false }); }
    finally { btn?.classList.remove("is-loading"); if (btn) btn.disabled = false; }
  }

  const Actions = {
    async refreshPainel() {
      try {
        const [estacao, eventos, stats] = await Promise.all([api.estacao(), api.eventos(), api.estatisticas()]);
        store.set({ online: true, estacao, eventos, stats });
      } catch (e) { store.set({ online: false }); }
    },

    async refreshTabela() {
      if (store.get("tabela").modo !== "lista") return;
      const { sessoes } = await api.listar(store.get("filtroStatus"));
      store.set({ tabela: { modo: "lista", sessoes, meta: null } });
    },

    async refreshAll() {
      await Promise.all([Actions.refreshPainel(), Actions.refreshTabela().catch(() => {})]);
      Router.current()?.refresh?.();
    },

    async encerrar(id, btn) {
      await withFeedback(btn, async () => {
        const s = await api.encerrar(id);
        Toast.get().success(`Sessão ${s.codigo} encerrada`, `${fmt.kwh(s.energia_kwh)} em ${fmt.min(s.duracao_min)} · Total ${fmt.brl(s.custo_total)}`);
        Modal.get().open(Components.detalhe(s));
        await Actions.refreshAll();
      });
    },

    async detalhe(id) {
      try { Modal.get().open(Components.detalhe(await api.obter(id))); }
      catch (e) { Toast.get().error("Sessão não encontrada", e.message); }
    },
  };

  /* ────────────────────────────────────────────────────────────────────────
     8. VIEWS (Strategy) — cada uma expõe { title, subtitle, init, enter, refresh }
     ──────────────────────────────────────────────────────────────────────── */
  const DashboardView = {
    title: "Painel do eletroposto",
    subtitle: "Monitoramento em tempo real dos pontos de recarga",
    init() {
      store.subscribe("estacao", (e) => {
        if (!e) return;
        $("#gauge").innerHTML = Components.gauge(e);
        const n = NIVEL[e.nivel];
        const badge = $("#nivelBadge");
        badge.className = `badge ${n.cls}`;
        badge.textContent = n.label;
        $("#points").innerHTML = e.pontos.map(Components.point).join("");
      });
      store.subscribe("eventos", (ev) => {
        $("#events").innerHTML = ev.length
          ? ev.slice(0, 25).map(Components.event).join("")
          : `<li>${Components.empty("Nenhuma mensagem OCPP ainda.")}</li>`;
      });
      store.subscribe("stats", (s) => {
        if (!s) return;
        $("#kpis").innerHTML = [
          Components.kpi({ label: "Faturamento", value: fmt.brl(s.faturamento_total), hint: `Ticket médio ${fmt.brl(s.ticket_medio)}`, icon: ICON.money }),
          Components.kpi({ label: "Energia fornecida", value: fmt.kwh(s.energia_total_kwh), hint: `${num(s.energia_media_kwh, 2)} kWh por sessão`, icon: ICON.bolt, accent: "var(--primary-2)" }),
          Components.kpi({ label: "Sessões", value: String(s.total_sessoes), hint: `${s.sessoes_ativas} ativas · ${s.sessoes_encerradas} encerradas`, icon: ICON.list, accent: "var(--violet)" }),
          Components.kpi({ label: "CO₂ evitado", value: `${num(s.co2_evitado_kg, 1)} kg`, hint: `~${num(s.km_gerados, 0)} km de autonomia`, icon: ICON.leaf, accent: "#34d399" }),
        ].join("");
      });
    },
  };

  const NovaSessaoView = {
    title: "Nova sessão",
    subtitle: "Cadastre um veículo — o backend aplica Power Management e tarifa dinâmica",
    veiculoAtual: "hatch",

    init() {
      const cfg = store.get("config");
      const form = $("#formSessao");

      $("#tiposUsuario").innerHTML = cfg.tipos_usuario.map((t, i) =>
        `<label><input type="radio" name="tipo_usuario" value="${esc(t)}" ${i === 0 ? "checked" : ""}/>${esc(t)}</label>`).join("");

      $("#veiculos").innerHTML = Object.entries(cfg.veiculos).map(([id, v], i) =>
        `<label class="vehicle"><input type="radio" name="veiculo_id" value="${id}" ${i === 0 ? "checked" : ""}/>
          <span class="vehicle__emoji" aria-hidden="true">${EMOJI_VEICULO[id] ?? "🔌"}</span>
          <strong>${esc(v.nome)}</strong><small>${v.bateria_kwh} kWh · até ${num(v.potencia_max, 1)} kW</small></label>`).join("");

      const horas = [...Array(24).keys()].map((h) => `<option value="${h}">${fmt.hora(h)}</option>`).join("");
      $("#hora").innerHTML = horas;
      $("#hora").value = new Date().getHours();

      store.subscribe("estacao", (e) => e && this.renderPontos(e));

      const preview = debounce(() => this.renderPreview(), 250);
      form.addEventListener("input", (ev) => { this.syncControles(ev.target); preview(); });
      form.addEventListener("submit", (ev) => { ev.preventDefault(); this.submit(); });
      this.syncControles();
    },

    enter(params = {}) {
      if (params.ponto) $("#ponto").value = params.ponto;
      this.renderPreview();
      setTimeout(() => $("#cliente").focus(), 50);
    },

    renderPontos(e) {
      const sel = $("#ponto");
      const atual = sel.value;
      const livres = e.pontos.filter((p) => p.livre);
      sel.innerHTML = `<option value="">Automático (1º livre)</option>` +
        livres.map((p) => `<option value="${p.ponto}">Ponto #${p.ponto}</option>`).join("");
      if (livres.some((p) => String(p.ponto) === atual)) sel.value = atual;
      $("#btnCadastrar").disabled = livres.length === 0;
      if (!livres.length) $("#formError").textContent = "Todos os pontos estão ocupados. Encerre uma sessão no painel.";
      else if ($("#formError").textContent.startsWith("Todos")) $("#formError").textContent = "";
    },

    /** Mantém os sliders coerentes: SOC alvo > inicial e potência ≤ limite do veículo. */
    syncControles(alvo) {
      const cfg = store.get("config");
      const veiculoId = $("input[name=veiculo_id]:checked").value;
      const v = cfg.veiculos[veiculoId];
      const pot = $("#potencia");
      if (veiculoId !== this.veiculoAtual || !alvo) {
        pot.min = cfg.potencia_min_kw;
        pot.max = v.potencia_max;
        pot.value = v.potencia_max;
        this.veiculoAtual = veiculoId;
      }
      const ini = $("#socInicial"), fim = $("#socAlvo");
      if (+fim.value <= +ini.value) {
        if (alvo === ini) fim.value = Math.min(100, +ini.value + 1);
        else ini.value = Math.max(0, +fim.value - 1);
      }
      $("#socInicialOut").textContent = `${ini.value}%`;
      $("#socAlvoOut").textContent = `${fim.value}%`;
      $("#potenciaOut").textContent = fmt.kw(pot.value);
      $$("#formSessao input[type=range]").forEach((r) => r.style.setProperty("--p", `${((r.value - r.min) / (r.max - r.min || 1)) * 100}%`));
    },

    dados() {
      const f = new FormData($("#formSessao"));
      return {
        cliente: f.get("cliente").trim(),
        tipo_usuario: f.get("tipo_usuario"),
        veiculo_id: f.get("veiculo_id"),
        soc_inicial: +f.get("soc_inicial"),
        soc_alvo: +f.get("soc_alvo"),
        potencia_kw: +f.get("potencia_kw"),
        hora_inicio: +f.get("hora_inicio"),
        ponto: f.get("ponto") ? +f.get("ponto") : null,
        encerrar_agora: f.get("encerrar_agora") === "on",
      };
    },

    async renderPreview() {
      const d = this.dados();
      const v = store.get("config").veiculos[d.veiculo_id];
      const energia = ((d.soc_alvo - d.soc_inicial) / 100) * v.bateria_kwh;
      const tempo = Math.ceil((energia / d.potencia_kw) * 60);
      try {
        const { simulacao: s } = await api.tarifas({ hora: d.hora_inicio, tipo_usuario: d.tipo_usuario, energia_kwh: energia.toFixed(2) });
        const p = PERIODO[s.periodo];
        $("#preview").innerHTML = `
          <ul class="preview-list">
            <li><span>Veículo</span><strong>${EMOJI_VEICULO[d.veiculo_id]} ${esc(v.nome)}</strong></li>
            <li><span>Energia a carregar</span><strong>${fmt.kwh(energia)}</strong></li>
            <li><span>Tempo estimado</span><strong>${fmt.min(tempo)}</strong></li>
            <li><span>Período</span><strong><span class="badge ${p.cls}">${p.label}</span></strong></li>
            <li><span>Tarifa</span><strong>${fmt.brl(s.tarifa_kwh)}/kWh</strong></li>
            ${s.desconto > 0 ? `<li><span>Desconto</span><strong>− ${fmt.brl(s.desconto)}</strong></li>` : ""}
            <li><span>Taxa de serviço</span><strong>${fmt.brl(s.taxa_servico)}</strong></li>
          </ul>
          <div class="preview-total"><small>Custo estimado</small><strong>${fmt.brl(s.custo_total)}</strong></div>
          <p class="note">${s.regra_especial ? esc(s.regra_especial) + ". " : ""}Estimativa calculada pelo backend com a demanda atual (${fmt.kw(s.demanda_atual_kw)}).
          O Power Management pode reduzir a potência se a estação estiver acima de 80%.</p>`;
      } catch (e) {
        $("#preview").innerHTML = Components.empty(e.message);
      }
    },

    async submit() {
      const d = this.dados();
      const erro = $("#formError");
      const nome = $("#cliente");
      erro.textContent = "";
      nome.removeAttribute("aria-invalid");
      if (d.cliente.length < 2) {
        erro.textContent = "Informe o nome do cliente (mínimo 2 caracteres).";
        nome.setAttribute("aria-invalid", "true");
        nome.focus();
        return;
      }
      await withFeedback($("#btnCadastrar"), async () => {
        const s = await api.cadastrar(d);
        if (s.status === "encerrada") {
          Toast.get().success(`Sessão ${s.codigo} concluída`, `Total ${fmt.brl(s.custo_total)}`);
          Modal.get().open(Components.detalhe(s));
        } else if (s.potencia_alocada_kw < s.potencia_solicitada_kw) {
          Toast.get().warn(`Sessão ${s.codigo} iniciada com redução`, `Power Management: ${fmt.kw(s.potencia_solicitada_kw)} → ${fmt.kw(s.potencia_alocada_kw)}`);
        } else {
          Toast.get().success(`Sessão ${s.codigo} iniciada`, `Ponto #${s.ponto} · ${fmt.kw(s.potencia_alocada_kw)}`);
        }
        nome.value = "";
        await Actions.refreshAll();
        if (s.status === "ativa") Router.go("dashboard");
      });
    },
  };

  const SessoesView = {
    title: "Sessões",
    subtitle: "Liste, busque e ordene — algoritmos executados no backend Python",

    init() {
      store.subscribe("tabela", (t) => this.render(t));

      $("#buscaChave").addEventListener("change", (e) => {
        const porCliente = e.target.value === "cliente";
        $("#buscaAlgoritmo").disabled = porCliente;
        $("#buscaAlgoritmo").value = porCliente ? "linear" : "binaria";
        $("#buscaValor").placeholder = porCliente ? "Ex.: Ana" : "Ex.: 7 ou CG-0007";
      });

      $("#formBusca").addEventListener("submit", async (e) => {
        e.preventDefault();
        const valor = $("#buscaValor").value.trim();
        if (!valor) return Toast.get().warn("Digite algo para buscar");
        await withFeedback(e.submitter, async () => {
          const r = await api.buscar($("#buscaChave").value, valor, $("#buscaAlgoritmo").value);
          store.set({ tabela: { modo: "busca", sessoes: r.resultados, meta: r } });
          if (!r.encontrados) Toast.get().warn("Nenhuma sessão encontrada", `${r.comparacoes} comparações realizadas`);
        });
      });

      $("#formOrdenar").addEventListener("submit", async (e) => {
        e.preventDefault();
        await withFeedback(e.submitter, async () => {
          const r = await api.ordenar($("#ordCriterio").value, $("#ordOrdem").value, $("#ordAlgoritmo").value);
          store.set({ tabela: { modo: "ordenacao", sessoes: r.sessoes, meta: r } });
        });
      });

      $("#btnLimparFiltro").addEventListener("click", () => this.voltarLista());

      $("#filtroStatus").addEventListener("click", (e) => {
        const chip = e.target.closest(".chip");
        if (!chip) return;
        $$(".chip", e.currentTarget).forEach((c) => c.classList.toggle("is-active", c === chip));
        store.set({ filtroStatus: chip.dataset.status });
        this.voltarLista();
      });

      const tbody = $("#tabelaSessoes");
      tbody.addEventListener("click", (e) => {
        if (e.target.closest("[data-encerrar]")) return;         // tratado globalmente
        const tr = e.target.closest("tr[data-id]");
        if (tr) Actions.detalhe(tr.dataset.id);
      });
      tbody.addEventListener("keydown", (e) => {
        const tr = e.target.closest("tr[data-id]");
        if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); Actions.detalhe(tr.dataset.id); }
      });
    },

    enter() { Actions.refreshTabela().catch((e) => Toast.get().error("Erro", e.message)); },

    voltarLista() {
      store.set({ tabela: { modo: "lista", sessoes: store.get("tabela").sessoes, meta: null } });
      Actions.refreshTabela().catch(() => {});
    },

    render({ modo, sessoes, meta }) {
      const titulos = { lista: "Todas as sessões", busca: "Resultado da busca", ordenacao: "Sessões ordenadas" };
      $("#tabelaTitulo").textContent = titulos[modo];
      $("#tabelaSessoes").innerHTML = sessoes.length
        ? sessoes.map(Components.row).join("")
        : `<tr><td colspan="10">${Components.empty(modo === "busca" ? "Nenhum resultado para esta busca." : "Nenhuma sessão cadastrada. Use “Cenário demo” ou cadastre uma nova.", modo === "busca" ? ICON.search : ICON.list)}</td></tr>`;

      const panel = $("#algoPanel");
      if (!meta) { panel.hidden = true; return; }
      const cell = (label, value) => `<div><small>${label}</small><strong>${esc(value)}</strong></div>`;
      panel.innerHTML = modo === "busca"
        ? [cell("Algoritmo", meta.algoritmo), cell("Complexidade", meta.complexidade), cell("Tamanho (n)", meta.tamanho_lista),
           cell("Comparações", meta.comparacoes), cell("Encontrados", meta.encontrados), cell("Tempo", `${meta.tempo_ms} ms`)].join("")
        : [cell("Algoritmo", meta.algoritmo), cell("Complexidade", meta.complexidade), cell("n", meta.n),
           cell("Comparações", meta.metricas.comparacoes),
           meta.metricas.trocas !== undefined ? cell("Trocas", meta.metricas.trocas) : cell("Escritas", meta.metricas.escritas),
           cell("n·log₂n (ref.)", meta.referencia_teorica.n_log2_n), cell("n² (ref.)", meta.referencia_teorica.n_quadrado),
           cell("Tempo", `${meta.metricas.tempo_ms} ms`)].join("");
      panel.hidden = false;
    },
  };

  const TarifasView = {
    title: "Estatísticas & Tarifação",
    subtitle: "Indicadores calculados no backend e regras de tarifa dinâmica",

    init() {
      const cfg = store.get("config");
      $("#simHora").innerHTML = [...Array(24).keys()].map((h) => `<option value="${h}">${fmt.hora(h)}</option>`).join("");
      $("#simHora").value = 19;
      $("#simTipo").innerHTML = cfg.tipos_usuario.map((t) => `<option>${esc(t)}</option>`).join("");
      $("#formSimulador").addEventListener("submit", (e) => { e.preventDefault(); this.simular(e.submitter); });
      store.subscribe("stats", (s) => s && Router.isActive(this) && this.renderStats(s));
    },

    async enter() {
      try {
        const t = await api.tarifas();
        $("#periodoAtual").className = `badge ${PERIODO[t.periodo_atual].cls}`;
        $("#periodoAtual").textContent = `Agora: ${PERIODO[t.periodo_atual].label}`;
        $("#tarifas").innerHTML = t.periodos.map((p) => `<div class="tariff ${p.periodo === t.periodo_atual ? "is-current" : ""}">
          <span class="badge ${PERIODO[p.periodo].cls}">${PERIODO[p.periodo].label}</span>
          <strong>${fmt.brl(p.tarifa_kwh)}</strong><small>por kWh · ${esc(p.faixa)}</small></div>`).join("");
        $("#regras").innerHTML = t.regras.map((r) => `<li>${esc(r)}</li>`).join("");
      } catch (e) { Toast.get().error("Erro ao carregar tarifas", e.message); }
      const s = store.get("stats");
      if (s) this.renderStats(s);
      this.simular();
    },

    renderStats(s) {
      $("#statsKpis").innerHTML = [
        Components.kpi({ label: "Ticket médio", value: fmt.brl(s.ticket_medio), hint: `Mediana ${fmt.brl(s.mediana_custo)} (via Merge Sort)`, icon: ICON.money }),
        Components.kpi({ label: "Preço médio efetivo", value: `${fmt.brl(s.preco_medio_kwh)}/kWh`, hint: "incluindo taxas e descontos", icon: ICON.bolt, accent: "var(--primary-2)" }),
        Components.kpi({ label: "Duração média", value: fmt.min(Math.round(s.duracao_media_min)), hint: `${num(s.energia_media_kwh, 2)} kWh em média`, icon: ICON.clock, accent: "var(--violet)" }),
        Components.kpi({ label: "Maior consumo", value: s.maior_consumo ? fmt.kwh(s.maior_consumo.energia_kwh) : "—", hint: s.maior_consumo ? `${s.maior_consumo.codigo} · ${s.maior_consumo.cliente}` : "", icon: ICON.car, accent: "var(--warn)" }),
        Components.kpi({ label: "Menor consumo", value: s.menor_consumo ? fmt.kwh(s.menor_consumo.energia_kwh) : "—", hint: s.menor_consumo ? `${s.menor_consumo.codigo} · ${s.menor_consumo.cliente}` : "", icon: ICON.leaf, accent: "#34d399" }),
      ].join("");

      $("#barsUsuario").innerHTML = Components.bars(
        Object.entries(s.por_tipo_usuario).map(([label, v]) => ({ label: `${label} (${v.sessoes})`, value: v.receita })),
        { valueFmt: fmt.brl, colors: ["var(--info)", "var(--primary)", "var(--violet)"] });
      $("#barsPeriodo").innerHTML = Components.bars(
        Object.entries(s.por_periodo).map(([k, v]) => ({ label: PERIODO[k].label, value: v.sessoes })),
        { valueFmt: (v) => `${v} sessões`, colors: ["var(--violet)", "var(--info)", "var(--crit)"] });
      animateBars();
    },

    async simular(btn) {
      await withFeedback(btn, async () => {
        const { simulacao: s } = await api.tarifas({ hora: $("#simHora").value, tipo_usuario: $("#simTipo").value, energia_kwh: $("#simEnergia").value });
        $("#simResultado").innerHTML = `<ul class="receipt">
          <li><span>Período</span><span><span class="badge ${PERIODO[s.periodo].cls}">${PERIODO[s.periodo].label}</span></span></li>
          <li><span>Tarifa base → aplicada</span><span class="mono">${fmt.brl(s.tarifa_base)} → ${fmt.brl(s.tarifa_kwh)}</span></li>
          ${s.acrescimo_kwh > 0 ? `<li><span>Acréscimo alta demanda</span><span class="mono">+ ${fmt.brl(s.acrescimo_kwh)}/kWh</span></li>` : ""}
          <li><span>Energia</span><span class="mono">${fmt.brl(s.custo_energia)}</span></li>
          ${s.desconto > 0 ? `<li><span>Desconto</span><span class="mono">− ${fmt.brl(s.desconto)}</span></li>` : ""}
          <li><span>Taxa de serviço</span><span class="mono">${fmt.brl(s.taxa_servico)}</span></li>
          <li class="total"><span>Total</span><span class="mono">${fmt.brl(s.custo_total)}</span></li></ul>
          ${s.regra_especial ? `<p class="note">${esc(s.regra_especial)}</p>` : ""}`;
      });
    },
  };

  const ResumoView = {
    title: "Resumo final",
    subtitle: "Relatório consolidado da operação do eletroposto",

    init() {
      $("#btnCsv").href = api.csvUrl();
      $("#btnPrint").addEventListener("click", () => window.print());
    },

    async enter() {
      $("#resumo").innerHTML = `<div class="skeleton"></div>`;
      try { this.render(await api.resumo()); }
      catch (e) { $("#resumo").innerHTML = Components.empty(e.message); }
    },

    render(r) {
      const s = r.indicadores;
      const tabelaTop = r.top_sessoes.length
        ? `<div class="table-wrap"><table class="table" style="min-width:0"><thead><tr><th>ID</th><th>Cliente</th><th>Energia</th><th>Tempo</th><th>Custo</th></tr></thead><tbody>
            ${r.top_sessoes.map((x) => `<tr data-id="${x.id}"><td class="num">${esc(x.codigo)}</td><td class="client">${esc(x.cliente)}<small>${esc(x.tipo_usuario)}</small></td>
              <td class="num">${fmt.kwh(x.energia_kwh)}</td><td class="num">${fmt.min(x.duracao_min)}</td><td class="num">${fmt.brl(x.custo_total)}</td></tr>`).join("")}
           </tbody></table></div>`
        : Components.empty("Nenhuma sessão encerrada.");

      $("#resumo").innerHTML = `<div class="report">
        <div class="report__hero">
          <h2>⚡ ChargeGrid Intelligence — Relatório da estação</h2>
          <p>Gerado em ${fmt.data(r.gerado_em)} · ${r.estacao.pontos} pontos · ${num(r.estacao.capacidade_kw, 0)} kW de capacidade ·
             ${s.sessoes_encerradas} sessões encerradas, ${s.sessoes_ativas} em andamento</p>
        </div>
        <div class="kpis" style="margin:0">
          ${Components.kpi({ label: "Faturamento total", value: fmt.brl(s.faturamento_total), icon: ICON.money })}
          ${Components.kpi({ label: "Energia total", value: fmt.kwh(s.energia_total_kwh), icon: ICON.bolt, accent: "var(--primary-2)" })}
          ${Components.kpi({ label: "Ticket médio", value: fmt.brl(s.ticket_medio), hint: `Mediana ${fmt.brl(s.mediana_custo)}`, icon: ICON.list, accent: "var(--violet)" })}
          ${Components.kpi({ label: "Impacto ambiental", value: `${num(s.co2_evitado_kg, 1)} kg CO₂`, hint: `~${num(s.km_gerados, 0)} km elétricos`, icon: ICON.leaf, accent: "#34d399" })}
        </div>
        <div class="grid grid--2">
          <article class="card"><header class="card__header"><h2>Top 5 sessões por custo</h2><span class="badge badge--violet">Merge Sort desc</span></header>${tabelaTop}</article>
          <article class="card"><header class="card__header"><h2>Ranking de clientes</h2><span class="badge badge--violet">Merge Sort desc</span></header>
            ${r.ranking_clientes.length ? `<ol class="rank">${r.ranking_clientes.map((c, i) => `<li><span class="rank__pos">${i + 1}</span>
              <div>${esc(c.cliente)}<small>${c.sessoes} sessão(ões) · ${fmt.kwh(c.energia_kwh)}</small></div><strong>${fmt.brl(c.gasto)}</strong></li>`).join("")}</ol>`
              : Components.empty("Sem clientes ainda.")}
          </article>
          <article class="card"><header class="card__header"><h2>Algoritmos utilizados</h2></header>
            <div class="table-wrap"><table class="table" style="min-width:0"><thead><tr><th>Operação</th><th>Algoritmo</th><th>Big-O</th></tr></thead><tbody>
              ${r.algoritmos.map((a) => `<tr><td>${esc(a.operacao)}</td><td>${esc(a.algoritmo)}</td><td class="num">${esc(a.complexidade)}</td></tr>`).join("")}
            </tbody></table></div>
          </article>
          <article class="card"><header class="card__header"><h2>Destaques</h2></header>
            <ul class="receipt">
              <li><span>Sessão mais cara</span><span class="mono">${s.sessao_mais_cara ? `${esc(s.sessao_mais_cara.codigo)} · ${fmt.brl(s.sessao_mais_cara.custo_total)}` : "—"}</span></li>
              <li><span>Maior consumo</span><span class="mono">${s.maior_consumo ? `${esc(s.maior_consumo.codigo)} · ${fmt.kwh(s.maior_consumo.energia_kwh)}` : "—"}</span></li>
              <li><span>Menor consumo</span><span class="mono">${s.menor_consumo ? `${esc(s.menor_consumo.codigo)} · ${fmt.kwh(s.menor_consumo.energia_kwh)}` : "—"}</span></li>
              <li><span>Duração média</span><span class="mono">${fmt.min(Math.round(s.duracao_media_min))}</span></li>
              <li><span>Preço médio efetivo</span><span class="mono">${fmt.brl(s.preco_medio_kwh)}/kWh</span></li>
              <li><span>Sessões em andamento</span><span class="mono">${r.sessoes_ativas.length}</span></li>
            </ul>
          </article>
        </div>
      </div>`;
      $$("#resumo tr[data-id]").forEach((tr) => tr.addEventListener("click", () => Actions.detalhe(tr.dataset.id)));
    },
  };

  function animateBars() {
    requestAnimationFrame(() => $$(".bar__fill[data-w]").forEach((b) => (b.style.width = `${b.dataset.w}%`)));
  }

  /* ────────────────────────────────────────────────────────────────────────
     9. ROUTER — escolhe a View (Strategy) ativa
     ──────────────────────────────────────────────────────────────────────── */
  const Router = (() => {
    const views = { dashboard: DashboardView, nova: NovaSessaoView, sessoes: SessoesView, tarifas: TarifasView, resumo: ResumoView };
    let atual = "dashboard";
    return {
      init() { Object.values(views).forEach((v) => v.init?.()); },
      current: () => views[atual],
      isActive: (view) => views[atual] === view,
      go(nome, params) {
        if (!views[nome]) return;
        atual = nome;
        $$(".view").forEach((s) => { const on = s.id === `view-${nome}`; s.hidden = !on; s.classList.toggle("is-visible", on); });
        $$(".nav__item").forEach((b) => { const on = b.dataset.view === nome; b.classList.toggle("is-active", on); b.toggleAttribute("aria-current", on); });
        $("#viewTitle").textContent = views[nome].title;
        $("#viewSubtitle").textContent = views[nome].subtitle;
        $("#sidebar").classList.remove("is-open");
        $("#menuToggle").setAttribute("aria-expanded", "false");
        history.replaceState(null, "", `#${nome}`);
        views[nome].enter?.(params);
        window.scrollTo({ top: 0, behavior: "smooth" });
      },
    };
  })();

  /* ────────────────────────────────────────────────────────────────────────
     10. BOOTSTRAP
     ──────────────────────────────────────────────────────────────────────── */
  function bindGlobal() {
    $$(".nav__item").forEach((b) => b.addEventListener("click", () => Router.go(b.dataset.view)));

    // Delegação de eventos: qualquer botão [data-encerrar] / [data-goto] da página.
    document.addEventListener("click", (e) => {
      const enc = e.target.closest("[data-encerrar]");
      if (enc) { e.stopPropagation(); Actions.encerrar(enc.dataset.encerrar, enc); return; }
      const go = e.target.closest("[data-goto]");
      if (go) Router.go(go.dataset.goto, { ponto: go.dataset.ponto });
    });

    $("#menuToggle").addEventListener("click", () => {
      const open = $("#sidebar").classList.toggle("is-open");
      $("#menuToggle").setAttribute("aria-expanded", String(open));
    });

    $("#btnDemo").addEventListener("click", (e) => withFeedback(e.currentTarget, async () => {
      const r = await api.demo();
      Toast.get().success("Cenário de demonstração carregado", `${r.total_sessoes} sessões na memória`);
      await Actions.refreshAll();
    }));

    $("#btnReset").addEventListener("click", (e) => {
      if (!confirm("Apagar todas as sessões da memória do servidor?")) return;
      withFeedback(e.currentTarget, async () => {
        await api.reset();
        Toast.get().success("Memória reiniciada");
        await Actions.refreshAll();
      });
    });

    store.subscribe("online", (on) => {
      const el = $("#apiStatus");
      el.classList.toggle("is-online", on === true);
      el.classList.toggle("is-offline", on === false);
      $(".label", el).textContent = on ? "API online" : "API offline";
    });
  }

  async function bootstrap() {
    bindGlobal();
    try {
      const config = await api.config();
      store.set({ config, online: true });
    } catch (e) {
      store.set({ online: false });
      $("#kpis").innerHTML = Components.empty(`${e.message} Execute: python backend/app.py`);
      Toast.get().error("API indisponível", e.message);
      return;
    }
    Router.init();
    await Actions.refreshAll();
    const inicial = location.hash.slice(1);
    Router.go(["dashboard", "nova", "sessoes", "tarifas", "resumo"].includes(inicial) ? inicial : "dashboard");

    // Polling: mantém o painel atualizado (pausa quando a aba está oculta).
    setInterval(() => { if (!document.hidden) Actions.refreshPainel(); }, POLLING_MS);
  }

  document.addEventListener("DOMContentLoaded", bootstrap);
})();
