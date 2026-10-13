/* Username Generator — interface. Toda a lógica de negócio fica no Python (core/); aqui só tela. */
(() => {
'use strict';

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
// O token da execução vem na URL; guardamos na sessão para sobreviver a um F5 e tiramos da barra de endereço.
let storedKey = '';
try { storedKey = sessionStorage.getItem('k') || ''; } catch (_) {}
const KEY = new URLSearchParams(location.search).get('k') || storedKey;
try { sessionStorage.setItem('k', KEY); } catch (e) { /* sem storage: só não sobrevive ao F5 */ }
try { history.replaceState(null, '', location.pathname); } catch (_) {}

const LOG_DOM_MAX = 1500;
const S = {
  meta: null, p: null, mode: 'random', tokens: {}, proxyChoice: null, proxyDefault: false,
  state: { running: false, stopping: false, platform: null, status: { key: 'idle', label: 'Parado' },
           counts: { done: 0, valid: 0, invalid: 0, error: 0 }, total: 0, progress: 0, quota: '', subtitle: '' },
  epoch: 0, after: 0, failures: 0, proxyRe: null, pending: false, navigating: false, filter: 'all',
};

/* ---------- API ---------- */
async function api(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const r = await fetch('/api/' + path, {
      signal: controller.signal,
      method: body === undefined ? 'GET' : 'POST',
      headers: { 'X-App-Token': KEY, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await r.json();
    S.failures = 0; $('#offline').hidden = true;
    if (!r.ok || data.ok === false) {
      data.ok = false;
      if (r.status === 401) data.error = 'Sessão expirada. Reabra o aplicativo.';
      if (path !== 'state') toast(data.error || 'Não foi possível concluir a ação.');
    }
    return data;
  } catch (e) {
    if (++S.failures >= 3) $('#offline').hidden = false;
    return { ok: false, error: 'Sem conexão com o aplicativo. Tente novamente.', offline: true };
  } finally { clearTimeout(timeout); }
}

/* ---------- Helpers de DOM ---------- */
const val = (id) => $(id).value;
const chk = (id) => $(id).checked;
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}
function icon(id) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'ic');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', '#' + id);
  svg.appendChild(use);
  return svg;
}

let toastTimer;
function toast(message) {
  const n = $('#toast'); n.textContent = message; n.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { n.hidden = true; }, 4500);
}

function platformLogo(platform) {
  const logo = el('span', 'platform-logo');
  logo.setAttribute('aria-hidden', 'true');
  logo.style.setProperty('--platform-icon', `url("icons/${(platform.icon_slug || platform.name.toLowerCase())}.svg")`);
  return logo;
}
function platformMark(platform) {
  const mark = el('span', 'mk'); mark.appendChild(platformLogo(platform)); return mark;
}

/* ---------- Construção inicial ---------- */
function buildNav() {
  const nav = $('#nav');
  for (const p of S.meta.platforms) {
    const b = el('button', 'nav-item');
    b.dataset.platform = p.name;
    b.dataset.tip = p.name; b.setAttribute('aria-label', p.name);
    b.append(platformMark(p), el('span', 'nm', p.name));
    b.addEventListener('click', () => openPlatform(p.name));
    nav.appendChild(b);
  }
  $('#nav-home').addEventListener('click', goHome);
}

function buildHome() {
  const list = $('#plist');
  $('#platform-count').textContent = `${S.meta.platforms.length} plataformas disponíveis`;
  for (const p of S.meta.platforms) {
    const row = el('button', 'prow');
    row.dataset.name = p.name.toLowerCase();
    const body = el('div');
    body.append(el('div', 'pn', p.name), el('div', 'pd', p.desc), el('div', 'pt', p.tags.join('  ·  ')));
    row.append(platformMark(p), body, icon('i-arrow'));
    row.addEventListener('click', () => openPlatform(p.name));
    list.appendChild(row);
  }
}

function buildModes() {
  const wrap = $('#modes');
  for (const m of S.meta.modes) {
    const b = el('button', 'mode', m.title);
    b.dataset.mode = m.key; b.dataset.lock = '';
    b.setAttribute('role', 'radio');
    b.addEventListener('click', () => selectMode(m.key));
    wrap.appendChild(b);
  }
}

const animations = new WeakMap();
async function animateVisibility(node, visible) {
  const previous = animations.get(node);
  if (previous) previous.cancel();
  if (node.hidden === !visible && !previous) return;
  node.hidden = false;
  node.inert = !visible;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches || !node.animate) {
    node.hidden = !visible; animations.delete(node); return;
  }
  const motion = node.animate(visible ? [{opacity: 0, transform: 'translateY(6px)'}, {opacity: 1, transform: 'translateY(0)'}]
    : [{opacity: 1}, {opacity: 0}], {duration: 150, easing: 'ease-out'});
  animations.set(node, motion);
  try {await motion.finished;} catch (_) {return;}
  if (animations.get(node) === motion) {node.hidden = !visible; animations.delete(node);}
}
async function showScreen(id) {
  const next = $('#' + id), previous = $$('.screen').find(node => !node.hidden && node !== next);
  if (previous) await animateVisibility(previous, false);
  await animateVisibility(next, true);
}

/* ---------- Telas ---------- */
function setCurrent(name) {
  $('#nav-home').setAttribute('aria-current', name ? 'false' : 'page');
  for (const button of $$('[data-feature]')) button.removeAttribute('aria-current');
  for (const b of $$('.nav-item[data-platform]')) {
    if (b.dataset.platform === name) b.setAttribute('aria-current', 'page');
    else b.removeAttribute('aria-current');
  }
}

async function goHome() {
  if (S.navigating || S.pending) return;
  S.navigating = true;
  try {
  if (!$('#work').hidden) {
    const r = await api('leave', {});
    if (!r.ok) return pollOnce();
  }
  await showScreen('home');
  setCurrent(null);
  } finally { S.navigating = false; }
}

async function openPlatform(name) {
  if (S.navigating || S.pending) return;
  S.navigating = true;
  try {
  const r = await api('select', { platform: name });
  if (!r.ok) return pollOnce();               // bloqueado enquanto roda: o aviso já está no log
  await pollOnce();                           // traz o painel já zerado (se trocou de plataforma)
  configure(S.meta.platforms.find((p) => p.name === name));
  await showScreen('work');
  setCurrent(name);
  } finally { S.navigating = false; }
}

function configure(p) {
  if (S.p) S.tokens[S.p.name] = val('#f-token');
  if (S.p?.name !== p.name) S.proxyChoice = null;
  S.p = p;
  const saved = S.tokens[p.name];
  $('#f-token').value = saved === undefined ? p.default_token : saved;

  $('#p-mark').replaceChildren(platformLogo(p));
  $('#p-name').textContent = p.name;
  $('#p-tags').textContent = p.tags.join('  ·  ');
  $('#p-desc').textContent = p.desc;
  $('#valid-label').textContent = p.lookup_only ? 'Não encontrados' : 'Disponíveis';
  $('.filter[data-filter="valid"]').textContent = p.lookup_only ? 'Não encontrados' : 'Disponíveis';
  clearTimeout($('#btn-copy').flashTimer);
  $('#btn-copy').classList.remove('ok');
  $('#btn-copy use').setAttribute('href', '#i-copy');
  $('#btn-copy span').textContent = p.lookup_only ? 'Copiar resultados' : 'Copiar disponíveis';
  $('#btn-copy').setAttribute('aria-label', p.lookup_only ? 'Copiar resultados' : 'Copiar disponíveis');

  for (const b of $$('.mode')) b.hidden = !p.modes.includes(b.dataset.mode);
  if (!p.modes.includes(S.mode)) S.mode = p.modes[0];
  selectMode(S.mode);

  $('#f-length').min = p.min_len; $('#f-length').max = p.max_len;
  if (+val('#f-length') < p.min_len || +val('#f-length') > p.max_len) $('#f-length').value = Math.max(p.min_len, Math.min(5, p.max_len));
  $('#lbl-length').textContent = `Quantidade de letras (${p.min_len}–${p.max_len})`;
  $('#lbl-sep').textContent = `Separar com ${p.sep} (${p.sep_name})`;

  $('#sec-token').hidden = !p.has_token;
  $('#lbl-token').textContent = p.token_title;
  // dica curta (ex.: client_id:client_secret) vai no placeholder; frase longa vira texto de ajuda
  const shortHint = p.token_hint.length <= 28;
  $('#f-token').placeholder = shortHint ? p.token_hint : '';
  const help = [shortHint ? '' : p.token_hint[0].toUpperCase() + p.token_hint.slice(1) + '.', p.token_help].filter(Boolean).join(' ');
  $('#token-help').textContent = help;
  $('#token-help').hidden = !help;

  const usesProxy = useProxiesForRun();
  $('#sec-proxy').hidden = !usesProxy;
  $('#lbl-proxy').textContent = p.needs_proxy ? 'Proxies (obrigatório)' : 'Proxies (opcional)';

  $('#path').textContent = p.display_file || p.file;
  $('#path').title = p.file;
  clearInvalid();
  updateProxyCount();
  refreshStart();
}

function selectMode(key) {
  S.mode = key;
  for (const b of $$('.mode')) {
    b.setAttribute('aria-checked', String(b.dataset.mode === key));
    b.tabIndex = b.dataset.mode === key ? 0 : -1;
  }
  const group = { random: 'random', en: 'words', pt: 'words', es: 'words', name: 'name', check: 'check' }[key];
  for (const g of ['random', 'words', 'name', 'check']) $('#opt-' + g).hidden = g !== group;
  $('#sec-amount').hidden = key === 'check';
  const count = S.meta?.verb_counts?.[key];
  $('#verb-vocabulary-count').textContent = count ? `${Number(count).toLocaleString(I18n.language)} verbos e expressões disponíveis neste idioma` : '';
  clearInvalid();
}

/* ---------- Proxies ---------- */
function parseProxies() {
  const good = new Set(); let bad = 0;
  for (let line of val('#f-proxies').split(/\r?\n/)) {
    line = line.trim();
    if (!line || line.startsWith('#')) continue;
    if (S.proxyRe.test(line)) good.add(line.includes('://') ? line : 'http://' + line);
    else bad++;
  }
  return { good: good.size, bad };
}

function updateProxyCount() {
  const { good, bad } = parseProxies();
  const n = $('#proxy-count');
  n.textContent = `${good} ${good === 1 ? 'proxy válido' : 'proxies válidos'}` + (bad ? `  ·  ${bad} ${bad === 1 ? 'linha ignorada' : 'linhas ignoradas'}` : '');
  n.classList.toggle('ok', good > 0);
  refreshStart();
}

function useProxiesForRun() {
  return !!(S.p && (S.p.needs_proxy || S.p.proxy_optional) && parseProxies().good > 0 &&
    (S.proxyChoice ?? Preferences.current.use_proxies));
}
function refreshProxyChoice() {
  const count = parseProxies().good, button = $('#use-saved-proxies');
  const supported = !!(S.p && (S.p.needs_proxy || S.p.proxy_optional));
  const enabled = useProxiesForRun();
  $('#proxy-run-choice').hidden = !S.p || count === 0;
  button.disabled = !supported || S.pending || S.state.running;
  button.setAttribute('aria-pressed', String(enabled));
  button.classList.toggle('selected', enabled);
  $('#proxy-run-label').textContent = enabled ? 'Usando proxies das configurações' : 'Usar os proxies das configurações?';
  $('#proxy-run-description').textContent = supported
    ? `${count} proxies salvos · ${enabled ? 'Clique para usar conexão direta' : 'Clique para usar nesta execução'}`
    : 'Esta plataforma usa conexão direta.';
  $('#sec-proxy').hidden = !enabled;
}
function importProxies(file) { void ProxyManager.importFile(file); }

/* ---------- Botões Iniciar / Parar ---------- */
function refreshStart() {
  refreshProxyChoice();
  const b = $('#btn-start'), st = S.state, p = S.p;
  b.replaceChildren();
  if (S.pending) {
    b.disabled = true; b.append(el('i', 'spin'), 'Iniciando…');
  } else if (st.running) {
    b.disabled = true;
    b.append(el('i', 'spin'), 'Executando…');
  } else if (p && useProxiesForRun() && p.needs_proxy && parseProxies().good === 0) {
    b.disabled = true; b.append('Adicione proxies');
  } else if (p && p.token_required && !(new RegExp(p.token_pattern).test(val('#f-token').trim()))) {
    b.disabled = true; b.append('Informe as credenciais');
  } else {
    b.disabled = !p; b.append(icon('i-play'), 'Iniciar verificação');
  }
  $('#btn-stop').disabled = !st.running || st.stopping;
  $('#btn-stop').lastChild.textContent = st.stopping ? 'Parando…' : 'Parar';
}

function setLocked(locked) {
  for (const n of $$('[data-lock]')) n.disabled = locked;
  document.body.classList.toggle('running', locked);
  $('#nav-home').classList.toggle('locked', locked);
  for (const b of $$('.nav-item[data-platform]')) b.classList.toggle('locked', locked && b.dataset.platform !== S.state.platform);
}

async function start() {
  if ($('#btn-start').disabled || !S.p || Preferences.modalOpen) return;
  clearInvalid();
  S.pending = true; refreshStart(); setLocked(true);
  try {
  if (!(await ProxyManager.flush())) { Preferences.open(); return; }
  const r = await api('start', {
    platform: S.p.name, mode: S.mode,
    amount: val('#f-amount'), length: val('#f-length'), base_name: val('#f-name'), list: val('#f-list'),
    two_words: chk('#sw-two'), digits: chk('#sw-digits'), use_sep: chk('#sw-sep'),
    suffixes: chk('#sw-suffix'), name_digits: chk('#sw-namedigits'),
    name_language: val('#f-name-language'),
    token: val('#f-token'), proxies: val('#f-proxies'), use_proxies: useProxiesForRun(),
  });
  if (!r.ok) {
    setLocked(S.state.running);
    $('#form-error').textContent = r.error || 'Não foi possível iniciar.';
    $('#form-error').hidden = false;
    if (r.field) markInvalid(r.field);
  }
  await pollOnce();
  } finally { S.pending = false; setLocked(S.state.running); refreshStart(); }
}

const FIELD_ID = { amount: '#f-amount', length: '#f-length', base_name: '#f-name', list: '#f-list', token: '#f-token', proxies: '#f-proxies' };
function markInvalid(field) {
  const n = FIELD_ID[field] ? $(FIELD_ID[field]) : null;
  if (n) { n.classList.add('invalid'); n.setAttribute('aria-invalid', 'true'); n.setAttribute('aria-describedby', 'form-error'); n.focus(); }
}
function clearInvalid() {
  $('#form-error').hidden = true;
  for (const n of $$('.invalid')) { n.classList.remove('invalid'); n.removeAttribute('aria-invalid'); n.removeAttribute('aria-describedby'); }
}

/* ---------- Estado vindo do servidor ---------- */
function applyState(st) {
  const wasRunning = S.state.running;
  S.state = st;
  const s = $('#status');
  s.dataset.state = st.status.key;
  $('#status-text').textContent = st.status.label;
  $('#subtitle').textContent = st.subtitle;
  $('#quota').textContent = st.quota;
  for (const k of ['done', 'valid', 'invalid', 'error']) $('#st-' + k).textContent = st.counts[k];
  const pct = Math.floor(st.progress * 100);
  $('#bar').style.width = (st.progress * 100).toFixed(1) + '%';
  $('#pct').textContent = pct + '%';
  $('#progress').setAttribute('aria-valuenow', String(pct));
  if (wasRunning !== st.running) setLocked(st.running || S.pending);
  refreshStart();
}

/* ---------- Log ---------- */
const logEl = () => $('#log');

function ensureEmpty() {
  const log = logEl();
  const has = log.querySelector('.row:not([hidden])');
  let e = log.querySelector('.empty');
  if (!has && !e) log.appendChild(el('div', 'empty', S.filter !== 'all' || val('#log-search') ? 'Nenhum resultado para este filtro.' : 'Pronto para começar. Configure a geração e inicie sua primeira verificação.'));
  else if (has && e) e.remove();
}

function clearLogDom() { logEl().replaceChildren(); ensureEmpty(); }

function rowFor(e) {
  const r = el('div', 'row ' + e.tag);
  r.append(el('span', 't', e.t), el('span', 'mkd'));
  if (e.name !== undefined) {
    r.append(el('span', 'nm', e.name), el('span', 'ix', `${e.i}/${e.n}`), el('span', 'st', e.text));
    r.title = e.name;
  } else {
    r.append(el('span', 'msg', e.text));
  }
  return r;
}

function filterLogs() {
  const query = val('#log-search').toLocaleLowerCase();
  for (const row of $$('.row', logEl())) row.hidden = (S.filter !== 'all' && !row.classList.contains(S.filter)) || !row.textContent.toLocaleLowerCase().includes(query);
  ensureEmpty();
}

function appendLogs(entries) {
  const log = logEl();
  const stick = log.scrollHeight - log.scrollTop - log.clientHeight < 48;
  const frag = document.createDocumentFragment();
  for (const e of entries) frag.appendChild(rowFor(e));
  log.appendChild(frag);
  const rows = log.querySelectorAll('.row');
  for (let i = 0; i < rows.length - LOG_DOM_MAX; i++) rows[i].remove();
  filterLogs();
  if (stick && Preferences.current.auto_scroll) log.scrollTop = log.scrollHeight;
}

/* ---------- Polling ---------- */
let queue = Promise.resolve();
function pollOnce() { queue = queue.then(doPoll, doPoll); return queue; }

async function doPoll() {
  const r = await api(`poll?after=${S.after}&epoch=${S.epoch}`);
  if (r.offline || r.ok === false) return;
  if (r.epoch !== S.epoch) { S.epoch = r.epoch; S.after = 0; clearLogDom(); }
  if (r.logs.length) { appendLogs(r.logs); S.after = r.logs[r.logs.length - 1].id; }
  applyState(r.state);
}

async function loop() {
  try { await pollOnce(); } catch (_) { $('#offline').hidden = false; }
  setTimeout(loop, S.failures ? 1500 : S.state.running ? 200 : 800);
}

/* ---------- Ações do log ---------- */
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch (e) { /* tenta o plano B */ }
  const t = el('textarea'); t.value = text; t.style.cssText = 'position:fixed;opacity:0';
  document.body.appendChild(t); t.select();
  let ok = false; try { ok = document.execCommand('copy'); } catch (e) { /* ignora */ }
  t.remove(); return ok;
}

function flash(btn, text) {
  clearTimeout(btn.flashTimer);
  const span = $('span', btn), old = S.p && S.p.lookup_only ? 'Copiar resultados' : 'Copiar disponíveis';
  btn.classList.add('ok'); span.textContent = text;
  btn.firstChild.firstChild.setAttribute('href', '#i-check');
  btn.flashTimer = setTimeout(() => { btn.classList.remove('ok'); span.textContent = old; btn.firstChild.firstChild.setAttribute('href', '#i-copy'); }, 1600);
}

async function copyValid() {
  const r = await api('valid', {});
  if (!r.ok) return pollOnce();
  if (await copyText(r.text)) {
    await api('log', { text: `${r.count} usernames copiados para a área de transferência.` });
    flash($('#btn-copy'), 'Copiado');
  } else {
    await api('log', { text: 'Não consegui acessar a área de transferência.', tag: 'warn' });
  }
  pollOnce();
}

/* ---------- Eventos ---------- */
function bind() {
  window.addEventListener('preferences-saved', () => {
    if (S.proxyDefault !== Preferences.current.use_proxies) {
      S.proxyDefault = Preferences.current.use_proxies; S.proxyChoice = null;
    }
    refreshStart();
  });
  for (const btn of $$('.log-actions .btn')) btn.setAttribute('aria-label', btn.textContent.trim());
  $('#nav-home').setAttribute('aria-label', 'Início');
  $('#theme').setAttribute('aria-label', 'Alternar tema');
  $('#platform-search').addEventListener('input', () => {
    const query = val('#platform-search');
    let count = 0;
    for (const row of $$('.prow')) {
      const visible = PlatformSearch.matches(row.dataset.name, query);
      if (visible) count++;
      animateVisibility(row, visible);
    }
    $('#no-platforms').hidden = count > 0;
  });
  $('#log-search').addEventListener('input', filterLogs);
  for (const btn of $$('.filter')) btn.addEventListener('click', () => {
    S.filter = btn.dataset.filter;
    for (const n of $$('.filter')) { n.classList.toggle('active', n === btn); n.setAttribute('aria-pressed', String(n === btn)); }
    filterLogs();
  });
  $('#modes').addEventListener('keydown', e => {
    if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
    const options = $$('.mode:not([hidden]):not(:disabled)');
    if (!options.length) return;
    e.preventDefault();
    let i = options.indexOf(document.activeElement);
    i = e.key === 'Home' ? 0 : e.key === 'End' ? options.length - 1 : (i + (['ArrowDown', 'ArrowRight'].includes(e.key) ? 1 : -1) + options.length) % options.length;
    options[i].click(); options[i].focus();
  });
  $('#use-saved-proxies').addEventListener('click', () => {
    if ($('#use-saved-proxies').disabled) return;
    S.proxyChoice = !useProxiesForRun(); refreshStart();
  });
  $('#btn-start').addEventListener('click', start);
  $('#btn-stop').addEventListener('click', async () => {
    if ($('#btn-stop').disabled) return;
    if (Preferences.current.confirm_stop && !(await ConfirmAction.ask('Cancelar verificação?'))) return;
    if (!S.state.running || S.state.stopping) return;
    await api('stop', {}); pollOnce();
  });
  $('#btn-copy').addEventListener('click', copyValid);
  $('#btn-folder').addEventListener('click', async () => { const r = await api('open-folder', {}); if (!r.ok) pollOnce(); });
  $('#btn-clear').addEventListener('click', async () => { await api('clear-log', {}); pollOnce(); });
  $('#theme').addEventListener('click', () => Preferences.toggleTheme());

  $('#proxy-import').addEventListener('click', () => $('#proxy-file').click());
  $('#proxy-file').addEventListener('change', (e) => { const f = e.target.files[0]; if (f) importProxies(f); e.target.value = ''; });
  $('#proxy-clear').addEventListener('click', () => void ProxyManager.clear());
  $('#f-proxies').addEventListener('input', updateProxyCount);
  $('#f-token').addEventListener('input', refreshStart);

  for (const n of $$('.input')) n.addEventListener('input', () => { n.classList.remove('invalid'); n.removeAttribute('aria-invalid'); n.removeAttribute('aria-describedby'); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.matches('.config input.input') && !Preferences.modalOpen && !e.isComposing) { e.preventDefault(); start(); }
  });
}

/* ---------- Início ---------- */
async function init() {
  const m = await api('state');
  if (m.offline || m.ok === false) {
    $('#offline').hidden = false;
    document.body.classList.remove('booting');
    if (m.offline) setTimeout(init, 2000);
    else $('#offline').textContent = m.error || 'Não foi possível abrir o aplicativo.';
    return;
  }
  S.meta = m; S.state = m.state; S.epoch = m.epoch;
  S.proxyDefault = !!m.settings?.use_proxies;
  S.proxyRe = new RegExp(m.proxy_pattern);
  $('#version').textContent = m.version;
  document.title = m.title;


  buildNav(); buildHome(); buildModes(); bind();
  $('#f-proxies').value = m.proxies;
  window.addEventListener('proxy-list-changed', updateProxyCount);
  ProxyManager.init(m.proxies, m.proxy_pattern, api);
  clearLogDom();

  if (m.state.platform) {                      // página recarregada com uma execução em andamento
    configure(S.meta.platforms.find((p) => p.name === m.state.platform));
    $('#home').hidden = true; $('#work').hidden = false;
    setCurrent(m.state.platform);
  } else {
    setCurrent(null);
  }
  setLocked(S.state.running);
  applyState(S.state);
  Preferences.init(m.settings || {}, api);
  refreshStart();
  FeaturesUI.mount({api, copyText, toast, platforms: m.platforms,
    async navigate(id) {
      if (S.navigating || S.pending) return;
      S.navigating = true;
      try {await showScreen(id); setCurrent('feature'); $('#nav-' + id).setAttribute('aria-current','page');}
      finally {S.navigating = false;}
    }});
  document.body.classList.remove('booting');
  loop();
}

init();
})();
