const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..', 'ui');
function runtime() {
  const context = vm.createContext({window: {}, document: {body: {}, documentElement: {}},
    navigator: {language: 'zh-TW'}, Node: {TEXT_NODE: 3}, Element: class {},
    MutationObserver: class {observe() {}}, NodeFilter: {SHOW_TEXT: 4, SHOW_ELEMENT: 1}});
  for (const file of ['translations.js', 'i18n.js']) vm.runInContext(fs.readFileSync(path.join(root, file), 'utf8'), context);
  return context.window.I18n;
}
test('all seven languages switch without restarting', () => {
  const i18n = runtime();
  const expected = {'pt-BR':'Configurações', en:'Settings', es:'Configuración',
    'zh-CN':'设置', ja:'設定', ru:'Настройки', fr:'Paramètres'};
  for (const [language, text] of Object.entries(expected)) {
    i18n.setLanguage(language);
    assert.equal(i18n.t('Configurações'), text);
  }
});
test('dynamic counters and compound logs are localized', () => {
  const i18n = runtime(); i18n.setLanguage('en');
  assert.equal(i18n.t('Quantidade de letras (3–20)'), 'Number of characters (3–20)');
  assert.equal(i18n.t('Concluído · Disponíveis: 3'), 'Completed · Available: 3');
  assert.equal(i18n.t('Iniciando (GitHub · Verificar usernames): 2 usernames'),
    'Starting (GitHub · Check usernames): 2 usernames');
});
test('usernames embedded in errors remain literal', () => {
  const i18n = runtime(); i18n.setLanguage('en');
  assert.equal(i18n.t('Concluído: resposta incompleta da plataforma.'),
    'Concluído: incomplete platform response.');
});
test('unknown service details remain readable', () => {
  const i18n = runtime(); i18n.setLanguage('ja');
  assert.equal(i18n.t('HTTP 503 / xyz'), 'HTTP 503 / xyz');
});
test('unsupported locales use a safe fallback', () => {
  const i18n = runtime();
  assert.equal(i18n.detect(), 'zh-CN');
  i18n.setLanguage('unsupported');
  assert.equal(i18n.language, 'pt-BR');
});
