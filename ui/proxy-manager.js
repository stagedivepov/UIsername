(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let text = '', revision = 0, savedRevision = 0, saving = null, timer, api, pattern;
  function status(message) {$('settings-proxy-status').textContent = message;}
  function error(message) {$('settings-proxy-error').textContent = message; $('settings-proxy-error').hidden = !message;}
  function sync() {
    for (const id of ['setting-proxies', 'f-proxies']) if ($(id).value !== text) $(id).value = text;
    const good = new Set(); let bad = 0;
    for (const raw of text.split(/\r?\n/)) {
      const line = raw.trim(); if (!line || line.startsWith('#')) continue;
      if (pattern.test(line)) good.add(line.includes('://') ? line : 'http://' + line); else bad++;
    }
    $('settings-proxy-count').textContent = I18n.t('{0} proxies com formato válido · {1} linhas ignoradas').replace('{0}', good.size).replace('{1}', bad);
    window.dispatchEvent(new CustomEvent('proxy-list-changed'));
  }
  function setText(value) {
    if (value.length > 400000) {error('A lista de proxies excede o limite de 400.000 caracteres.'); return false;}
    text = value; revision++; error(''); sync(); status('Salvando…');
    clearTimeout(timer); timer = setTimeout(() => void flush(), 450); return true;
  }
  async function flush() {
    clearTimeout(timer);
    if (saving) {await saving; return savedRevision === revision;}
    saving = (async () => {
      while (savedRevision < revision) {
        const version = revision, snapshot = text;
        let response;
        try {response = await api('proxies', {text: snapshot});} catch (_) {response = {ok:false};}
        if (!response.ok) {error(response.error || 'Não foi possível salvar. Verifique a permissão da pasta.'); status('Não salvo'); return;}
        savedRevision = version;
      }
      status('Alterações salvas automaticamente');
    })();
    try {await saving;} finally {saving = null;}
    return savedRevision === revision;
  }
  async function importFile(file) {
    if (file.size > 1000000) {error('Importe um arquivo de texto de até 1 MB.'); Preferences.open(); return;}
    try {
      const incoming = (await file.text()).replace(/^\uFEFF/, '').trim();
      if (setText((text.trim() ? text.trim() + '\n' : '') + incoming)) await flush();
    } catch (_) {error('Não consegui ler o arquivo de proxies.'); Preferences.open();}
  }
  function init(initial, regex, apiFunction) {
    api = apiFunction; pattern = new RegExp(regex); text = initial || ''; sync(); status('Alterações salvas automaticamente');
    for (const id of ['setting-proxies', 'f-proxies']) $(id).addEventListener('input', e => setText(e.target.value));
    $('settings-proxy-import').addEventListener('click', () => $('settings-proxy-file').click());
    $('settings-proxy-file').addEventListener('change', e => {if (e.target.files[0]) void importFile(e.target.files[0]); e.target.value = '';});
    $('settings-proxy-clear').addEventListener('click', () => {setText(''); void flush();});
    window.addEventListener('language-changed', sync);
  }
  window.ProxyManager = {init, setText, flush, importFile, clear() {setText(''); return flush();}};
})();
