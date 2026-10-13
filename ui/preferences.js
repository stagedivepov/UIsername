(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const defaults = {startup_mode: 'window', theme: 'dark', theme_animation: true, compact: false, auto_scroll: true, confirm_stop: true,
    default_amount: 100, username_interval: 0, batch_enabled: true, sidebar_collapsed: false, use_proxies: false};
  const systemTheme = matchMedia('(prefers-color-scheme: dark)');
  let saved = {...defaults}, api, firstRun = false, welcomeBusy = false;
  let desired = null, revision = 0, savedRevision = 0, saving = null, timer, closing = false;
  let applied = null;
  function apply(settings) {
    const language = settings.language || I18n.detect();
    if (I18n.language !== language) I18n.setLanguage(language);
    const theme = settings.theme === 'system' ? (systemTheme.matches ? 'dark' : 'light') : settings.theme;
    if (document.documentElement.dataset.theme !== theme) document.documentElement.dataset.theme = theme;
    if (!applied || applied.theme !== theme || applied.theme_animation !== settings.theme_animation) {
      SkyScene.setEnabled(theme === 'sky', settings.theme_animation);
      $('theme-motion-row').hidden = theme !== 'sky';
      $('theme-icon').setAttribute('href', theme === 'light' ? '#i-moon' : '#i-sun');
      $('theme-name').textContent = theme === 'light' ? 'Tema escuro' : 'Tema claro';
    }
    if (!applied || applied.compact !== settings.compact) document.body.classList.toggle('compact', settings.compact);
    if (!applied || applied.sidebar_collapsed !== settings.sidebar_collapsed) {
      document.body.classList.toggle('sidebar-collapsed', settings.sidebar_collapsed);
      $('sidebar').inert = !!settings.sidebar_collapsed;
      $('sidebar-toggle-icon').setAttribute('href', settings.sidebar_collapsed ? '#i-sidebar-closed' : '#i-sidebar');
      $('sidebar-toggle').setAttribute('aria-expanded', String(!settings.sidebar_collapsed));
      $('sidebar-toggle').setAttribute('aria-label', settings.sidebar_collapsed ? 'Mostrar barra lateral' : 'Ocultar barra lateral');
    }
    applied = {theme, theme_animation: settings.theme_animation, compact: settings.compact, sidebar_collapsed: settings.sidebar_collapsed};
  }
  function fill(settings) {
    $('setting-language').value = settings.language || I18n.detect();
    LanguagePicker.refresh();
    $('setting-theme').value = settings.theme;
    $('setting-startup_mode').value = settings.startup_mode;
    ThemePicker.refresh();
    $('setting-amount').value = settings.default_amount;
    $('setting-interval').value = Math.round(settings.username_interval * 1000);
    refreshSpeedPresets();
    for (const key of ['compact', 'auto_scroll', 'confirm_stop', 'batch_enabled', 'use_proxies', 'theme_animation']) $('setting-' + key).checked = settings[key];
  }
  function draft() {
    return {startup_mode: $('setting-startup_mode').value, language: $('setting-language').value, theme: $('setting-theme').value, theme_animation: $('setting-theme_animation').checked,
      default_amount: Number($('setting-amount').value), username_interval: Number($('setting-interval').value) / 1000,
      compact: $('setting-compact').checked, auto_scroll: $('setting-auto_scroll').checked,
      confirm_stop: $('setting-confirm_stop').checked, batch_enabled: $('setting-batch_enabled').checked, use_proxies: $('setting-use_proxies').checked, sidebar_collapsed: (desired || saved).sidebar_collapsed};
  }
  function error(message) {
    $('settings-error').textContent = message; $('settings-error').hidden = false;
    $('settings-save-status').textContent = 'Não salvo';
  }
  function capture() {
    const values = draft();
    if (!$('setting-amount').value.trim() || !Number.isInteger(values.default_amount) || values.default_amount < 1 || values.default_amount > 100000) {
      error('Use um número inteiro de 1 a 100.000.'); return false;
    }
    if (!$('setting-interval').value.trim() || !Number.isInteger(Number($('setting-interval').value)) || !Number.isFinite(values.username_interval) || values.username_interval < 0 || values.username_interval > 600) {
      error('Use um intervalo inteiro de 0 a 600.000 ms.'); return false;
    }
    const previous = desired || saved;
    if (Object.keys(values).every(key => values[key] === previous[key])) {
      $('settings-error').hidden = true; return true;
    }
    desired = values; revision++; apply(values);
    $('settings-error').hidden = true; $('settings-save-status').textContent = 'Salvando…';
    return true;
  }
  async function flush() {
    clearTimeout(timer);
    if (saving) {await saving; return savedRevision === revision;}
    saving = (async () => {
      while (desired && savedRevision < revision) {
        const version = revision, values = {...desired};
        let response;
        try {response = await api('settings', values);} catch (_) {response = {ok: false};}
        if (!response.ok) {error(response.error || 'Não foi possível salvar. Verifique a permissão da pasta.'); return;}
        saved = {...defaults, ...response.settings}; savedRevision = version;
        window.dispatchEvent(new CustomEvent('preferences-saved'));
      }
      if (savedRevision === revision) $('settings-save-status').textContent = 'Alterações salvas automaticamente';
    })();
    try {await saving;} finally {saving = null;}
    return savedRevision === revision;
  }
  function refreshSpeedPresets() {
    for (const button of document.querySelectorAll('[data-speed-ms]')) {
      const active = $('setting-interval').value.trim() !== '' && Number(button.dataset.speedMs) === Number($('setting-interval').value);
      button.setAttribute('aria-pressed', String(active));
    }
  }
  function schedule(event) {
    if (event?.target?.closest("[data-proxy-control]")) return;
    if (event?.type === "input" && event.target?.type === "checkbox") return;
    refreshSpeedPresets();
    clearTimeout(timer);
    if (!capture()) return;
    if (event?.type === 'change') void flush();
    else timer = setTimeout(() => void flush(), 450);
  }
  function open() {
    if (firstRun || welcomeBusy || closing || $('settings-dialog').open) return;
    fill(desired || saved); $('settings-error').hidden = true;
    $('settings-dialog').showModal();
  }
  async function close() {
    const dialog = $('settings-dialog');
    if (!dialog.open || closing) return;
    closing = true;
    try {
      if (!capture() || !(await flushAll())) return;
      if (dialog.open) dialog.close();
    } finally {closing = false;}
  }
  function init(settings, apiFunction) {
    api = apiFunction; saved = {...defaults, ...settings};
    for (const id of ['setting-language', 'welcome-language']) {
      for (const [code, name] of Object.entries(I18n.languages)) {
        const option = document.createElement('option'); option.value = code; option.textContent = name;
        option.lang = code; $(id).appendChild(option);
      }
      LanguagePicker.mount($(id));
    }
    ThemePicker.mount($('setting-theme')); fill(saved);
    apply(saved); $('f-amount').value = saved.default_amount;
    $('f-name-language').value = saved.language === 'es' ? 'es' : 'en';
    $('settings-version').textContent = $('version').textContent;
    $('sidebar-toggle').addEventListener('click', async () => {
      desired = {...(desired || saved), sidebar_collapsed: !document.body.classList.contains('sidebar-collapsed')};
      revision++; apply(desired); await flush();
    });
    $('settings-open').addEventListener('click', open);
    $('settings-close').addEventListener('click', () => void close());
    $('settings-dialog').addEventListener('cancel', event => {event.preventDefault(); void close();});
    const settingsDialog = $('settings-dialog');
    let backdropPointer = null;
    function outsideDialog(event) {
      const rect = settingsDialog.getBoundingClientRect();
      return event.target === settingsDialog &&
        (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom);
    }
    settingsDialog.addEventListener('pointerdown', event => {
      backdropPointer = event.button === 0 && outsideDialog(event) ? event.pointerId : null;
    });
    settingsDialog.addEventListener('pointerup', event => {
      const dismiss = backdropPointer === event.pointerId && outsideDialog(event);
      backdropPointer = null;
      if (dismiss) {event.preventDefault(); void close();}
    });
    settingsDialog.addEventListener('pointercancel', () => {backdropPointer = null;});
    settingsDialog.addEventListener('close', () => {backdropPointer = null;});
    for (const button of document.querySelectorAll('[data-speed-ms]')) button.addEventListener('click', () => {
      $('setting-interval').value = button.dataset.speedMs;
      $('setting-interval').dispatchEvent(new Event('change', {bubbles: true}));
    });
    $('settings-form').addEventListener('input', schedule);
    $('settings-form').addEventListener('change', schedule);
    $('settings-form').addEventListener('submit', event => {event.preventDefault(); schedule({type: 'change'});});
    $('settings-reset').addEventListener('click', () => {
      desired = {...defaults, language: (desired || saved).language};
      fill(desired); schedule({type: 'change'});
    });
    $('welcome-dialog').addEventListener('cancel', event => event.preventDefault());
    $('welcome-language').addEventListener('change', () => I18n.setLanguage($('welcome-language').value));
    $('welcome-form').addEventListener('submit', async event => {
      event.preventDefault(); if (welcomeBusy) return;
      welcomeBusy = true; $('welcome-error').hidden = true;
      const button = $('welcome-form').querySelector('.welcome-submit'); button.disabled = true;
      try {
        const response = await api('settings', {language: $('welcome-language').value});
        if (response.ok) {
          saved = {...defaults, ...response.settings}; apply(saved);
          $('f-name-language').value = saved.language === 'es' ? 'es' : 'en';
          firstRun = false; $('welcome-dialog').close(); $('nav-home').focus();
        } else {
          $('welcome-error').textContent = response.error || 'Não foi possível salvar. Verifique a permissão da pasta.';
          $('welcome-error').hidden = false;
        }
      } finally {welcomeBusy = false; button.disabled = false;}
    });
    systemTheme.addEventListener('change', () => apply(desired || saved));
    firstRun = !Object.hasOwn(I18n.languages, saved.language);
    if (firstRun) {$('welcome-language').value = I18n.language; LanguagePicker.refresh(); $('welcome-dialog').showModal();}
  }
  async function flushAll() {return (await flush()) && (await ProxyManager.flush());}
  window.Preferences = {init, open, flush: flushAll,
    get current() {return {...saved};},
    get modalOpen() {return $('welcome-dialog').open || $('settings-dialog').open || ConfirmAction.open;},
    async toggleTheme() {
      const theme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
      desired = {...(desired || saved), theme}; revision++; apply(desired);
      await flush();
    }};
})();
