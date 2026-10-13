/* Desktop tools. All server calls reuse the authenticated local API. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id),
    el = (tag, cls, text) => {
      const n = document.createElement(tag);
      if (cls) n.className = cls;
      if (text !== undefined) n.textContent = text;
      return n;
    };
  const STATES = {
    AVAILABLE: "Disponível confirmado",
    TAKEN: "Ocupado confirmado",
    UNKNOWN: "Inconclusivo",
    RATE_LIMITED: "Limite de requisições",
    AUTH_REQUIRED: "Autenticação necessária",
    ERROR: "Erro técnico",
    UNSUPPORTED: "Não suportado",
  };
  const STATUSES = {
    running: "Em execução",
    completed: "Concluído",
    cancelled: "Cancelado",
    interrupted: "Interrompido",
    failed: "Falha",
    exhausted: "Espaço esgotado",
    attempt_limit: "Limite de tentativas",
    stopped: "Interrompido",
    limit: "Limite atingido",
  };
  const BOOLS = [
    "lowercase",
    "uppercase",
    "numbers",
    "underscores",
    "require_vowel",
    "require_consonant",
    "no_adjacent_repeat",
    "no_repeated_sequences",
    "no_numeric_sequences",
    "pronounceable",
  ];
  const INTS = [
    "min_length",
    "max_length",
    "amount",
    "max_consecutive_digits",
    "max_attempts",
  ];
  const STRINGS = [
    "pattern",
    "allowed",
    "forbidden",
    "prefixes",
    "suffixes",
    "banned_words",
    "language",
  ];
  let api,
    copy,
    toast,
    navigate,
    platforms = [],
    presets = [],
    favorites = new Set(),
    names = [],
    selected = new Set(),
    namePage = 0,
    favoritesView = false;
  let jobs = {},
    rows = [],
    identityPage = 0,
    viewSid = "",
    genKey = "",
    identityKey = "",
    analyticsData = null,
    analyticsRevision = 0,
    lastAnalytics = 0;
  let presetBusy = false,
    generatorPending = false,
    identityPending = false;
  const size = 100;
  const locale = () => I18n.language,
    number = (n) =>
      Number(n || 0).toLocaleString(locale(), { maximumFractionDigits: 2 });
  const percent = (n) => (n === null ? "—" : number(n * 100) + "%"),
    date = (n) => new Date(n * 1000).toLocaleString(locale());
  function error(id, message) {
    $(id).textContent = message || "";
    $(id).hidden = !message;
  }
  function fail(id, response) {
    if (!response?.ok) {
      error(id, response?.error || "Não foi possível concluir a ação.");
      return true;
    }
    error(id, "");
    return false;
  }
  function download(text, name, type = "text/plain") {
    const link = el("a");
    const url = URL.createObjectURL(new Blob([text], { type }));
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function option(select, value, text) {
    const n = el("option", "", text);
    n.value = value;
    select.appendChild(n);
    return n;
  }
  function rules() {
    const result = {};
    for (const key of BOOLS) result[key] = $("rule-" + key).checked;
    for (const key of INTS) result[key] = Number($("rule-" + key).value);
    for (const key of STRINGS) result[key] = $("rule-" + key).value;
    return result;
  }
  function fillRules(rule) {
    for (const key of BOOLS) $("rule-" + key).checked = rule[key];
    for (const key of [...INTS, ...STRINGS]) $("rule-" + key).value = rule[key];
  }
  async function loadPresets(id) {
    const r = await api("generator/presets", {});
    if (fail("generator-error", r)) return;
    presets = r.rows;
    favorites = new Set(r.favorites);
    const current = id || $("generator-preset").value;
    $("generator-preset").replaceChildren();
    for (const p of presets) {
      const item = option($("generator-preset"), p.id, p.name);
      if (!p.builtin) item.dataset.noTranslate = "";
    }
    $("generator-preset").value = presets.some((p) => p.id === current)
      ? current
      : presets[0].id;
    $("preset-delete").disabled =
      $("generator-preset").value.startsWith("builtin:");
  }
  function loadPreset() {
    const p = presets.find((p) => p.id === $("generator-preset").value);
    if (!p) return;
    fillRules(p.rules);
    $("generator-preset-name").value = p.name;
    $("preset-delete").disabled = p.builtin;
    error("generator-error", "");
  }
  async function savePreset(asNew) {
    if (presetBusy) return;
    presetBusy = true;
    try {
      const id = $("generator-preset").value;
      const r = await api("generator/preset-save", {
        name: $("generator-preset-name").value,
        rules: rules(),
        id: !asNew && !id.startsWith("builtin:") ? id : undefined,
      });
      if (!fail("generator-error", r)) {
        await loadPresets(r.id);
        toast("Preset salvo.");
      }
    } finally {
      presetBusy = false;
    }
  }
  function showEstimate(estimate) {
    if (!estimate?.value) {
      $("generator-space").textContent = "";
      return;
    }
    let value = estimate.value;
    try {
      value = BigInt(value).toLocaleString(locale());
    } catch (_) {}
    $("generator-space").textContent =
      estimate.kind === "exact"
        ? `${value} combinações exatas`
        : `Até ${value} combinações; filtros podem reduzir esse total.`;
  }
  function selection() {
    $("generator-selection").textContent = `${selected.size} selecionados`;
    $("generator-to-identity").disabled =
      selected.size === 0 || selected.size > 100;
    $("generator-select-all").checked =
      displayNames().length > 0 && displayNames().every((n) => selected.has(n));
    $("generator-select-all").indeterminate =
      selected.size > 0 && !$("generator-select-all").checked;
  }
  function displayNames() {
    return favoritesView ? [...favorites] : names;
  }
  function renderNames() {
    const list = displayNames();
    namePage = Math.min(
      namePage,
      Math.max(0, Math.ceil(list.length / size) - 1),
    );
    const wrap = $("generator-names");
    wrap.replaceChildren();
    if (!list.length)
      wrap.appendChild(
        el(
          "p",
          "feature-empty",
          favoritesView
            ? "Nenhum favorito salvo."
            : "Gere uma prévia para explorar os resultados.",
        ),
      );
    for (const name of list.slice(namePage * size, (namePage + 1) * size)) {
      const row = el("div", "name-item"),
        label = el("label"),
        check = el("input");
      check.type = "checkbox";
      check.checked = selected.has(name);
      check.addEventListener("change", () => {
        check.checked ? selected.add(name) : selected.delete(name);
        selection();
      });
      const text = el("span", "name", name);
      text.dataset.noTranslate = "";
      label.append(check, text);
      const star = el(
        "button",
        "favorite-button",
        favorites.has(name) ? "★" : "☆",
      );
      star.type = "button";
      star.setAttribute("aria-label", "Favoritar nome");
      star.setAttribute("aria-pressed", String(favorites.has(name)));
      star.addEventListener("click", async () => {
        star.disabled = true;
        const active = !favorites.has(name);
        const r = await api("generator/favorite", { username: name, active });
        if (r.ok) {
          active ? favorites.add(name) : favorites.delete(name);
          renderNames();
        } else {
          star.disabled = false;
          error("generator-error", r.error);
        }
      });
      row.append(label, star);
      wrap.appendChild(row);
    }
    $("generator-page").textContent = list.length
      ? `${namePage + 1} / ${Math.ceil(list.length / size)}`
      : "0 / 0";
    $("generator-prev").disabled = namePage === 0;
    $("generator-next").disabled = (namePage + 1) * size >= list.length;
    selection();
  }
  async function generate(event) {
    event?.preventDefault();
    if (generatorPending || jobs.generator?.status === "running") return;
    generatorPending = true;
    $("generator-start").disabled = true;
    const r = await api("generator/start", { rules: rules() });
    generatorPending = false;
    if (fail("generator-error", r)) {
      $("generator-start").disabled = false;
      return;
    }
    favoritesView = false;
    $("generator-favorites").classList.remove("active");
    names = [];
    selected.clear();
    namePage = 0;
    renderNames();
    $("generator-summary").textContent = "Gerando prévia…";
    await poll();
  }
  async function estimate() {
    const button = $("generator-estimate");
    button.disabled = true;
    try {
      const r = await api("generator/estimate", { rules: rules() });
      if (!fail("generator-error", r)) showEstimate(r.estimate);
    } finally {
      button.disabled = false;
    }
  }
  function identityPayload(overrideNames, overridePlatforms) {
    const credentials = {};
    for (const p of platforms) {
      const field = $("credential-" + p.icon_slug);
      if (field && field.value.trim()) credentials[p.name] = field.value.trim();
    }
    return {
      names:
        overrideNames ||
        $("identity-names")
          .value.split(/[\n,;]+/)
          .map((n) => n.trim())
          .filter(Boolean),
      platforms:
        overridePlatforms ||
        [...$("identity-platforms").querySelectorAll("input:checked")].map(
          (n) => n.value,
        ),
      credentials,
      timeout: Number($("identity-timeout").value),
      concurrency: Number($("identity-concurrency").value),
      retries: Number($("identity-retries").value),
      auto_suggestions: $("identity-auto").checked,
    };
  }
  async function startIdentity(event, overrideNames, overridePlatforms) {
    event?.preventDefault();
    if (identityPending || jobs.identity?.status === "running") return;
    identityPending = true;
    $("identity-start").disabled = true;
    const r = await api(
      "identity/start",
      identityPayload(overrideNames, overridePlatforms),
    );
    identityPending = false;
    if (fail("identity-error", r)) {
      $("identity-start").disabled = false;
      return;
    }
    viewSid = r.id;
    rows = [];
    identityPage = 0;
    $("identity-history").value = "";
    identityKey = "";
    renderIdentity();
    await poll();
  }
  function normalizedRows() {
    const search = $("identity-result-search").value.toLocaleLowerCase(),
      status = $("identity-status").value;
    return FeaturesModel.filterResults(rows, search, status);
  }
  function renderIdentity() {
    const list = normalizedRows();
    identityPage = Math.min(
      identityPage,
      Math.max(0, Math.ceil(list.length / size) - 1),
    );
    const body = $("identity-results");
    body.replaceChildren();
    for (const r of list.slice(
      identityPage * size,
      (identityPage + 1) * size,
    )) {
      const row = el("tr"),
        platform = el("td", "", r.platform),
        username = el("td", "mono", r.username);
      username.dataset.noTranslate = "";
      if (r.suggestion)
        platform.appendChild(el("small", "", "Sugestão verificada"));
      const status = el("td"),
        badge = el("span", "result-status", STATES[r.status] || r.status);
      badge.dataset.status = r.status;
      status.append(badge, el("small", "", r.detail));
      const actions = el("td"),
        buttons = el("div", "result-actions");
      const copyButton = el("button", "btn ghost sm", "Copiar");
      copyButton.addEventListener("click", async () => {
        if (await copy(r.username)) toast("Copiado");
      });
      const repeat = el("button", "btn ghost sm", "Reverificar");
      repeat.disabled = jobs.identity?.status === "running" || identityPending;
      repeat.addEventListener("click", () =>
        startIdentity(null, [r.username], [r.platform]),
      );
      buttons.append(copyButton, repeat);
      const url = r.profile_url || r.signup_url;
      if (url) {
        try {
          const parsed = new URL(url);
          if (parsed.protocol === "https:") {
            const link = el(
              "a",
              "",
              r.profile_url ? "Abrir perfil" : "Abrir cadastro",
            );
            link.href = url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            buttons.appendChild(link);
          }
        } catch (_) {}
      }
      const suggestionList = el("div", "suggestion-list");
      for (const value of r.suggestions || []) {
        const button = el("button", "", value);
        button.dataset.noTranslate = "";
        button.title = "Verificar esta sugestão";
        button.disabled = jobs.identity?.status === "running";
        button.addEventListener("click", () =>
          startIdentity(null, [value], [r.platform]),
        );
        suggestionList.appendChild(button);
      }
      actions.append(buttons, suggestionList);
      row.append(platform, username, status, actions);
      body.appendChild(row);
    }
    const summary = FeaturesModel.identitySummary(rows);
    const { available, conclusive, unresolved } = summary;
    $("identity-consistency").textContent = rows.length
      ? summary.singleUsername
        ? `Disponível em ${available} de ${conclusive} plataformas verificadas conclusivamente. ${unresolved} plataformas sem confirmação.`
        : `Disponível em ${available} de ${conclusive} resultados conclusivos. ${unresolved} resultados sem confirmação.`
      : "Ainda não há resultados confirmados.";
    $("identity-breakdown").replaceChildren();
    for (const [state, count] of Object.entries(summary.counts).filter(
      ([state, count]) => count && state !== "AVAILABLE" && state !== "TAKEN",
    )) {
      if ($("identity-breakdown").childNodes.length)
        $("identity-breakdown").appendChild(document.createTextNode(" · "));
      $("identity-breakdown").append(
        el("span", "", STATES[state]),
        document.createTextNode(": " + number(count)),
      );
    }
    $("identity-empty").hidden = list.length > 0;
    $("identity-page").textContent = list.length
      ? `${identityPage + 1} / ${Math.ceil(list.length / size)}`
      : "0 / 0";
    $("identity-prev").disabled = identityPage === 0;
    $("identity-next").disabled = (identityPage + 1) * size >= list.length;
    $("identity-export").disabled = !viewSid;
  }
  async function loadHistory() {
    const r = await api("identity/history", {});
    if (!r.ok) return;
    const choice = $("identity-history").value;
    $("identity-history").replaceChildren();
    option($("identity-history"), "", "Consulta atual");
    const archivedGroup = document.createElement("optgroup"); archivedGroup.label = I18n.t("Sessões arquivadas");
    $("identity-history").appendChild(archivedGroup);
    for (const item of r.rows)
      option(
        item.archived ? archivedGroup : $("identity-history"),
        item.id,
        date(item.started) +
          " · " +
          (STATUSES[item.status] || item.status) +
          " · " +
          item.checked,
      );
    if (!archivedGroup.children.length) archivedGroup.remove();
    $("identity-history").value = choice;
  }
  async function openHistory() {
    const id = $("identity-history").value;
    if (!id) {
      rows = jobs.identity?.results || [];
      viewSid = jobs.identity?.id || "";
      renderIdentity();
      return;
    }
    const r = await api("identity/history", { id });
    if (fail("identity-error", r)) return;
    rows = r.rows;
    viewSid = id;
    identityPage = 0;
    renderIdentity();
  }
  async function exportIdentity() {
    if (!viewSid) return;
    const format = $("identity-format").value;
    const r = await api("identity/export", {
      id: viewSid,
      format,
      available_only: $("identity-export-available").checked,
    });
    if (!fail("identity-error", r))
      download(
        r.text,
        "UIsername-identity-" + viewSid + "." + format,
        format === "json" ? "application/json" : "text/csv",
      );
  }
  function filters() {
    return {
      platform: $("analytics-platform").value,
      period: $("analytics-period").value,
      search: $("analytics-search").value,
    };
  }
  async function refreshAnalytics() {
    const revision = ++analyticsRevision;
    const r = await api("analytics/query", filters());
    if (revision !== analyticsRevision) return;
    if (fail("analytics-error", r)) return;
    analyticsData = r.data;
    lastAnalytics = Date.now();
    renderAnalytics();
    if (r.data.warning) error("analytics-error", r.data.warning);
  }
  async function exportAnalytics(format) {
    const r = await api("analytics/export", { ...filters(), format });
    if (!fail("analytics-error", r))
      download(
        r.text,
        "UIsername-analytics." + format,
        format === "json" ? "application/json" : "text/csv",
      );
  }
  function svg(tag, attrs, text) {
    const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs || {}))
      n.setAttribute(k, String(v));
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function interactive(node, fn) {
    node.setAttribute("tabindex", "0");
    node.setAttribute("role", "button");
    node.addEventListener("click", fn);
    node.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        fn();
      }
    });
  }
  let lastTimelineKey = "",
    lastDistributionKey = "";
  function timeline(data) {
    const key = JSON.stringify(data) + $("analytics-period").value + locale();
    if (key === lastTimelineKey) return;
    lastTimelineKey = key;
    const wrap = $("analytics-timeline");
    wrap.replaceChildren();
    if (!data.length) {
      wrap.appendChild(
        el("p", "feature-empty", "Nenhuma verificação neste período."),
      );
      return;
    }
    const graph = svg("svg", {
        viewBox: "0 0 560 210",
        role: "group",
        "aria-label": "Verificações ao longo do tempo",
      }),
      max = Math.max(
        4,
        Math.ceil(Math.max(1, ...data.map((r) => r.verified)) / 4) * 4,
      ),
      start = data[0].at,
      end = data[data.length - 1].at;
    const x = (at) =>
        50 + (end === start ? 230 : ((at - start) / (end - start)) * 460),
      y = (value) => 165 - (value / max) * 140;
    for (let i = 0; i <= 4; i++) {
      const value = (max * i) / 4;
      graph.append(
        svg("line", {
          x1: 50,
          x2: 510,
          y1: y(value),
          y2: y(value),
          stroke: "var(--border)",
        }),
        svg(
          "text",
          { x: 42, y: y(value) + 4, "text-anchor": "end" },
          number(value),
        ),
      );
    }
    graph.appendChild(
      svg("polyline", {
        points: data.map((r) => `${x(r.at)},${y(r.verified)}`).join(" "),
        fill: "none",
        stroke: "var(--accent)",
        "stroke-width": 2,
      }),
    );
    for (const item of data) {
      const label = date(item.at) + " · " + number(item.verified);
      const dot = svg("circle", {
        cx: x(item.at),
        cy: y(item.verified),
        r: 4,
        fill: "var(--accent)",
        "aria-label": label,
      });
      dot.appendChild(svg("title", {}, label));
      interactive(dot, () => {
        $("timeline-detail").textContent = label;
      });
      graph.appendChild(dot);
    }
    graph.append(
      svg(
        "text",
        { x: 50, y: 195 },
        new Date(start * 1000).toLocaleString(
          locale(),
          ["hour", "day", "week"].includes($("analytics-period").value)
            ? {
                day: "2-digit",
                month: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              }
            : { day: "2-digit", month: "2-digit", year: "numeric" },
        ),
      ),
      svg(
        "text",
        { x: 510, y: 195, "text-anchor": "end" },
        new Date(end * 1000).toLocaleString(
          locale(),
          ["hour", "day", "week"].includes($("analytics-period").value)
            ? {
                day: "2-digit",
                month: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              }
            : { day: "2-digit", month: "2-digit", year: "numeric" },
        ),
      ),
    );
    wrap.appendChild(graph);
  }
  function distribution(data) {
    const key = [
      data.available,
      data.taken,
      data.unknown,
      data.errors,
      locale(),
    ].join(":");
    if (key === lastDistributionKey) return;
    lastDistributionKey = key;
    const wrap = $("analytics-distribution");
    wrap.replaceChildren();
    const parts = [
        ["Disponíveis confirmados", data.available, "var(--ok)"],
        ["Ocupados", data.taken, "var(--bad)"],
        ["Inconclusivos", data.unknown, "var(--accent)"],
        ["Erros", data.errors, "var(--subtle)"],
      ],
      total = parts.reduce((n, p) => n + p[1], 0);
    if (!total) {
      wrap.appendChild(
        el("p", "feature-empty", "Nenhum resultado neste período."),
      );
      return;
    }
    const graph = svg("svg", {
      viewBox: "0 0 200 150",
      role: "group",
      "aria-label": "Distribuição dos resultados",
    });
    const circumference = 2 * Math.PI * 49;
    let offset = 0;
    for (const [label, value, color] of parts) {
      if (!value) continue;
      const segment = svg("circle", {
        cx: 100,
        cy: 72,
        r: 49,
        fill: "none",
        stroke: color,
        "stroke-width": 16,
        "stroke-dasharray": `${(value / total) * circumference} ${circumference}`,
        "stroke-dashoffset": -offset,
        transform: "rotate(-90 100 72)",
        "aria-label": I18n.t(label) + " " + number(value),
      });
      const detail = () => {
        $("distribution-detail").textContent =
          I18n.t(label) +
          ": " +
          number(value) +
          " (" +
          percent(value / total) +
          ")";
      };
      interactive(segment, detail);
      graph.appendChild(segment);
      offset += (value / total) * circumference;
    }
    graph.appendChild(
      svg(
        "text",
        {
          x: 100,
          y: 76,
          "text-anchor": "middle",
          style: "font-size:20px;fill:var(--text)",
        },
        number(total),
      ),
    );
    wrap.appendChild(graph);
    const legend = el("div", "donut-legend");
    for (const [label, value, color] of parts) {
      const button = el("button"),
        key = el("i");
      key.style.background = color;
      button.append(key, el("span", "", label), el("b", "", number(value)));
      button.addEventListener("click", () => {
        $("distribution-detail").textContent =
          I18n.t(label) +
          ": " +
          number(value) +
          " (" +
          percent(value / total) +
          ")";
      });
      legend.appendChild(button);
    }
    wrap.appendChild(legend);
  }
  function renderAnalytics() {
    const data = analyticsData;
    if (!data) return;
    const stats = [
      ["Gerados", number(data.generated)],
      ["Verificados", number(data.verified)],
      ["Disponíveis confirmados", number(data.available)],
      ["Ocupados", number(data.taken)],
      ["Inconclusivos", number(data.unknown)],
      ["Erros de rede e API", number(data.errors)],
      ["Taxa de disponibilidade", percent(data.availability_rate)],
      ["Verificações por segundo", number(data.speed)],
      ["Tempo de processamento", number(data.processing_seconds) + " s"],
      ["Mais nomes disponíveis", data.best_platform || "—"],
    ];
    const wrap = $("analytics-stats");
    wrap.replaceChildren();
    for (const [label, value] of stats) {
      const card = el("div", "analytics-stat");
      card.append(el("strong", "", value), el("span", "", label));
      wrap.appendChild(card);
    }
    timeline(data.timeline);
    distribution(data);
    const metric = $("analytics-metric").value,
      max = Math.max(1, ...data.platforms.map((p) => p[metric]));
    const chart = $("analytics-platform-chart"),
      table = $("analytics-platform-rows");
    chart.replaceChildren();
    table.replaceChildren();
    for (const p of data.platforms) {
      const bar = el("button", "platform-bar"),
        track = el("span", "platform-bar-track"),
        fill = el("i");
      fill.style.width = (p[metric] / max) * 100 + "%";
      track.appendChild(fill);
      bar.append(
        el("span", "", p.platform === "local" ? "Geração local" : p.platform),
        track,
        el(
          "b",
          "",
          metric === "conclusive_rate" ? percent(p[metric]) : number(p[metric]),
        ),
      );
      bar.addEventListener("click", () => {
        $("analytics-platform").value = p.platform;
        refreshAnalytics();
      });
      chart.appendChild(bar);
      const row = el("tr");
      for (const text of [
        p.platform === "local" ? "Geração local" : p.platform,
        number(p.verified),
        number(p.speed) + "/s",
        percent(p.conclusive_rate),
        number(p.available),
      ])
        row.appendChild(el("td", "", text));
      table.appendChild(row);
    }
    renderSessionRows($("analytics-sessions"), data.sessions, false);
    renderSessionRows($("analytics-archived-sessions"), data.archived_sessions || [], true);
    $("analytics-empty").hidden = data.sessions.length > 0;
    $("analytics-archived-empty").hidden = (data.archived_sessions || []).length > 0;
    $("analytics-archived-count").textContent = number((data.archived_sessions || []).length);
  }
  const deleteConfirmations = new Map();
  function renderSessionRows(sessions, items, archived) {
    sessions.replaceChildren();
    for (const item of items) {
      const row = el("tr"),
        time = el("td", "", date(item.started)),
        id = el("small", "mono", item.id);
      id.dataset.noTranslate = "";
      time.appendChild(id);
      row.appendChild(time);
      for (const text of [
        item.platform === "multi"
          ? "Várias plataformas"
          : item.platform === "local"
            ? "Geração local"
            : item.platform,
        item.method === "identity" ? "Verificar identidade" : item.method,
        number(item.verified),
        number(item.available),
        number(item.duration) + " s",
        STATUSES[item.status] || item.status,
      ])
        row.appendChild(el("td", "", text));
      const actions = el("td"), group = el("div", "session-actions");
      const archive = el("button", "btn sm", archived ? "Restaurar" : "Arquivar");
      const remove = el("button", "btn sm session-delete", "Excluir");
      archive.type = remove.type = "button";
      archive.disabled = remove.disabled = item.status === "running";
      if (item.status === "running") group.title = "Aguarde a sessão terminar antes de alterar o histórico.";
      async function manage(action) {
        archive.disabled = remove.disabled = true;
        try {
          const response = await api("analytics/session", {id: item.id, action});
          if (fail("analytics-error", response)) return;
          if (action === "delete") {
            for (const kind of Object.keys(jobs)) if (jobs[kind].id === item.id) delete jobs[kind];
          }
          if (action === "delete" && viewSid === item.id) {
            viewSid = ""; rows = []; identityPage = 0; $("identity-history").value = ""; renderIdentity();
          }
          await loadHistory(); await refreshAnalytics();
        } finally {
          if (row.isConnected) archive.disabled = remove.disabled = item.status === "running";
        }
      }
      archive.addEventListener("click", () => void manage(archived ? "restore" : "archive"));
      let confirmUntil = deleteConfirmations.get(item.id) || 0;
      if (Date.now() < confirmUntil) remove.textContent = "Confirmar exclusão";
      remove.addEventListener("click", () => {
        if (Date.now() < confirmUntil) {deleteConfirmations.delete(item.id); void manage("delete"); return;}
        confirmUntil = Date.now() + 6000; deleteConfirmations.set(item.id, confirmUntil);
        remove.textContent = "Confirmar exclusão";
        remove.title = "Esta ação remove os resultados da sessão e atualiza as estatísticas.";
        setTimeout(() => {if (deleteConfirmations.get(item.id) !== confirmUntil) return; deleteConfirmations.delete(item.id); confirmUntil = 0; remove.textContent = "Excluir"; remove.removeAttribute("title");}, 6000);
      });
      group.append(archive, remove); actions.appendChild(group); row.appendChild(actions);
      sessions.appendChild(row);
    }
  }
  async function poll() {
    const r = await api("features/state", {});
    if (!r.ok) return;
    jobs = r.jobs;
    const gen = jobs.generator;
    if (gen) {
      const active = gen.status === "running";
      $("generator-start").disabled = active || generatorPending;
      $("generator-cancel").disabled = !active;
      $("generator-summary").textContent = active
        ? `${gen.done} nomes gerados · ${gen.attempts || 0} tentativas`
        : `${gen.names.length} de ${gen.requested || gen.total} nomes · ${STATUSES[gen.status] || gen.status}`;
      showEstimate(gen.estimate);
      const key = gen.id + ":" + gen.status + ":" + gen.names.length;
      if (key !== genKey) {
        genKey = key;
        if (gen.names.length) {
          names = gen.names;
          selected.clear();
          namePage = 0;
          renderNames();
        }
      }
      if (gen.error) error("generator-error", gen.error);
    }
    const identity = jobs.identity;
    if (identity) {
      const active = identity.status === "running";
      $("identity-start").disabled = active || identityPending;
      $("identity-cancel").disabled = !active;
      $("identity-repeat").disabled = active;
      $("identity-history").disabled = active;
      $("identity-progress").textContent =
        `${identity.done}/${identity.total} · ${STATUSES[identity.status] || identity.status}`;
      $("identity-bar").max = Math.max(1, identity.total);
      $("identity-bar").value = identity.done;
      const key = identity.id + ":" + identity.status + ":" + identity.done;
      if (key !== identityKey) {
        identityKey = key;
        if (!$("identity-history").value) {
          rows = identity.results;
          viewSid = identity.id;
          renderIdentity();
        }
        if (!active) await loadHistory();
      }
      if (identity.error) error("identity-error", identity.error);
    }
    if (!$("analytics").hidden && Date.now() - lastAnalytics > 2000)
      await refreshAnalytics();
    if (r.warning) error("analytics-error", r.warning);
  }
  async function loop() {
    try {
      await poll();
    } catch (_) {
      /* authenticated API displays connection state */
    }
    setTimeout(loop, document.hidden ? 2500 : 700);
  }
  async function mount(context) {
    ({ api, copyText: copy, toast, navigate, platforms } = context);
    for (const button of document.querySelectorAll("[data-feature]"))
      button.addEventListener("click", async () => {
        await navigate(button.dataset.feature);
        if (button.dataset.feature === "analytics") await refreshAnalytics();
      });
    for (const p of platforms) {
      const chip = el("label", "platform-chip"),
        check = el("input");
      check.type = "checkbox";
      check.value = p.name;
      check.checked = true;
      const image = el("img");
      image.src = "icons/" + encodeURIComponent(p.icon_slug) + ".svg";
      image.alt = "";
      chip.append(check, image, el("span", "", p.name));
      chip.dataset.platform = p.name;
      check.addEventListener("change", () => {
        $("identity-all").checked = [
          ...$("identity-platforms").querySelectorAll("input"),
        ].every((n) => n.checked);
      });
      $("identity-platforms").appendChild(chip);
      option($("analytics-platform"), p.name, p.name);
      if (p.has_token) {
        const label = el("label", "field"),
          field = el("input", "input");
        field.id = "credential-" + p.icon_slug;
        field.type = "password";
        field.autocomplete = "off";
        field.spellcheck = false;
        field.placeholder = p.token_hint;
        label.append(el("span", "hint", p.token_title), field);
        $("identity-credentials").appendChild(label);
      }
    }
    for (const [state, label] of Object.entries(STATES))
      option($("identity-status"), state, label);
    $("advanced-form").addEventListener("submit", generate);
    $("generator-estimate").addEventListener("click", estimate);
    $("generator-preset").addEventListener("change", loadPreset);
    $("generator-reset").addEventListener("click", loadPreset);
    $("preset-save").addEventListener("click", () => savePreset(false));
    $("preset-copy").addEventListener("click", () => savePreset(true));
    $("preset-delete").addEventListener("click", async () => {
      const id = $("generator-preset").value;
      if (id.startsWith("builtin:")) return;
      const r = await api("generator/preset-delete", { id });
      if (!fail("generator-error", r)) {
        await loadPresets();
        loadPreset();
      }
    });
    $("generator-cancel").addEventListener("click", async () => {
      const job = jobs.generator;
      if (!job || job.status !== "running") return;
      if (Preferences.current.confirm_stop && !(await ConfirmAction.ask("Cancelar geração?"))) return;
      if (jobs.generator?.id === job.id && jobs.generator.status === "running")
        await api("features/cancel", {id: job.id});
    });
    $("generator-select-all").addEventListener("change", () => {
      const all = $("generator-select-all").checked;
      for (const name of displayNames())
        all ? selected.add(name) : selected.delete(name);
      renderNames();
    });
    $("generator-favorites").addEventListener("click", () => {
      favoritesView = !favoritesView;
      selected.clear();
      namePage = 0;
      $("generator-favorites").classList.toggle("active", favoritesView);
      renderNames();
    });
    $("generator-prev").addEventListener("click", () => {
      namePage--;
      renderNames();
    });
    $("generator-next").addEventListener("click", () => {
      namePage++;
      renderNames();
    });
    $("generator-copy").addEventListener("click", async () => {
      if (
        await copy((selected.size ? [...selected] : displayNames()).join("\n"))
      )
        toast("Copiado");
    });
    $("generator-export").addEventListener("click", () =>
      download(
        (selected.size ? [...selected] : displayNames()).join("\n"),
        "UIsername-usernames.txt",
      ),
    );
    $("generator-to-identity").addEventListener("click", async () => {
      if (!selected.size || selected.size > 100) return;
      $("identity-names").value = [...selected].join("\n");
      await navigate("identity");
    });
    $("identity-form").addEventListener("submit", (event) =>
      startIdentity(event),
    );
    $("identity-cancel").addEventListener("click", async () => {
      const job = jobs.identity;
      if (!job || job.status !== "running") return;
      if (Preferences.current.confirm_stop && !(await ConfirmAction.ask("Cancelar verificação?"))) return;
      if (jobs.identity?.id === job.id && jobs.identity.status === "running")
        await api("features/cancel", {id: job.id});
    });
    $("identity-repeat").addEventListener("click", () => {
      const primary = rows.filter((r) => !r.suggestion);
      startIdentity(
        null,
        primary.length
          ? [...new Set(primary.map((r) => r.input_username || r.username))]
          : undefined,
        primary.length
          ? [...new Set(primary.map((r) => r.platform))]
          : undefined,
      );
    });
    $("identity-all").addEventListener("change", () => {
      for (const check of $("identity-platforms").querySelectorAll("input"))
        check.checked = $("identity-all").checked;
    });
    $("identity-platform-search").addEventListener("input", () => {
      for (const chip of $("identity-platforms").children)
        chip.hidden = !PlatformSearch.matches(
          chip.dataset.platform,
          $("identity-platform-search").value,
        );
    });
    for (const id of ["identity-result-search", "identity-status"])
      $(id).addEventListener("input", () => {
        identityPage = 0;
        renderIdentity();
      });
    $("identity-history").addEventListener("change", openHistory);
    $("identity-export").addEventListener("click", exportIdentity);
    $("identity-prev").addEventListener("click", () => {
      identityPage--;
      renderIdentity();
    });
    $("identity-next").addEventListener("click", () => {
      identityPage++;
      renderIdentity();
    });
    for (const id of ["analytics-platform", "analytics-period"])
      $(id).addEventListener("change", refreshAnalytics);
    $("analytics-refresh").addEventListener("click", refreshAnalytics);
    $("analytics-metric").addEventListener("change", renderAnalytics);
    $("analytics-csv").addEventListener("click", () => exportAnalytics("csv"));
    $("analytics-json").addEventListener("click", () =>
      exportAnalytics("json"),
    );
    let searchTimer;
    $("analytics-search").addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(refreshAnalytics, 250);
    });
    window.addEventListener("preferences-saved", () => {
      renderIdentity();
      renderAnalytics();
      showEstimate(jobs.generator?.estimate);
      void loadHistory();
    });
    await loadPresets();
    loadPreset();
    renderNames();
    renderIdentity();
    await loadHistory();
    loop();
  }
  window.FeaturesUI = { mount };
})();
