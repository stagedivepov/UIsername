/* Catalog-based localization. Usernames, paths, input values and credentials are never translated. */
(() => {
  'use strict';
  const languages = {'pt-BR': 'Português (Brasil)', en: 'English', es: 'Español',
    'zh-CN': '简体中文', ja: '日本語', ru: 'Русский', fr: 'Français'};
  const catalog = window.TRANSLATIONS;
  let language = 'pt-BR';
  const originals = new WeakMap();
  const attributes = new WeakMap();
  const skip = 'script,style,[data-no-translate],.row .nm,.row .ix,.row .t,#path';
  const escape = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const templates = Object.entries(catalog).filter(([key]) => /\{\d+\}/.test(key)).map(([key, values]) => {
    const ids = [...key.matchAll(/\{(\d+)\}/g)].map(m => m[1]);
    const pattern = key.split(/\{\d+\}/).map(escape).join('(.+?)');
    return {regex: new RegExp('^' + pattern + '$'), ids, values, literalName: key.startsWith('{0}:')};
  });
  function t(text, depth = 0) {
    if (language === 'pt-BR' || !text || depth > 5) return text;
    if (catalog[text]) return catalog[text][language] || catalog[text].en || text;
    for (const item of templates) {
      const match = item.regex.exec(text);
      if (match) {
        const values = Object.fromEntries(item.ids.map((id, i) => [id,
          item.literalName && id === '0' ? match[i + 1] : t(match[i + 1], depth + 1)]));
        return (item.values[language] || item.values.en).replace(/\{(\d+)\}/g, (_, id) => values[id]);
      }
    }
    if (text.includes(' · ') || text.includes('  ·  ')) return text.split(/(\s+·\s+)/).map(x => /^\s+·\s+$/.test(x) ? x : t(x, depth + 1)).join('');
    const indexed = /^(\[\d+\/\d+\]\s+)(.+)$/.exec(text);
    return indexed ? indexed[1] + t(indexed[2], depth + 1) : text;
  }
  function translateNode(node) {
    if (!node.parentElement || node.parentElement.closest(skip + ',textarea')) return;
    const current = node.nodeValue;
    const old = originals.get(node);
    const source = old && old.output === current ? old.source : current;
    const trimmed = source.trim();
    const output = trimmed ? source.replace(trimmed, () => t(trimmed)) : source;
    originals.set(node, {source, output});
    if (output !== current) node.nodeValue = output;
  }
  function translateAttributes(element) {
    if (element.closest(skip)) return;
    let saved = attributes.get(element);
    if (!saved) { saved = {}; attributes.set(element, saved); }
    for (const key of ['placeholder', 'aria-label', 'data-tip', 'title']) {
      if (key === 'title' && element.classList.contains('row')) continue;
      const current = element.getAttribute(key);
      if (current === null) continue;
      const old = saved[key];
      const source = old && old.output === current ? old.source : current;
      const output = t(source);
      saved[key] = {source, output};
      if (output !== current) element.setAttribute(key, output);
    }
  }
  function render(root = document.body) {
    if (root.nodeType === Node.TEXT_NODE) { translateNode(root); return; }
    if (!(root instanceof Element) || root.closest(skip)) return;
    translateAttributes(root);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.nodeType === Node.TEXT_NODE) translateNode(node);
      else translateAttributes(node);
    }
  }
  function setLanguage(value) {
    language = Object.hasOwn(languages, value) ? value : 'pt-BR';
    document.documentElement.lang = language;
    render();
  }
  new MutationObserver(records => {
    const roots = new Set();
    for (const record of records) {
      if (record.type === 'childList') for (const node of record.addedNodes) roots.add(node);
      else roots.add(record.target);
    }
    for (const root of roots) if (root.isConnected) render(root);
  }).observe(document.body, {subtree: true, childList: true, characterData: true, attributes: true,
    attributeFilter: ['placeholder', 'aria-label', 'data-tip', 'title']});
  window.I18n = {t, setLanguage, render, languages, get language() {return language;},
    detect() {
      const code = navigator.language || 'pt-BR';
      return /^pt/i.test(code) ? 'pt-BR' : /^zh/i.test(code) ? 'zh-CN' :
        Object.hasOwn(languages, code.split('-')[0]) ? code.split('-')[0] : 'en';
    }};
})();
