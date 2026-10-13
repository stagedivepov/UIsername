(() => {
  'use strict';
  const controls = new Map();
  const badges = {'pt-BR':'PT', en:'EN', es:'ES', 'zh-CN':'中', ja:'日', ru:'РУ', fr:'FR'};
  const subtitles = {'pt-BR':'Brasil', en:'English', es:'Español', 'zh-CN':'简体中文', ja:'日本語', ru:'Русский', fr:'Français'};
  function refresh() {for (const item of controls.values()) item.refresh();}
  function mount(select) {
    if (controls.has(select.id)) return;
    select.hidden = true;
    const trigger = document.createElement('button');
    trigger.type = 'button'; trigger.className = 'language-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox'); trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-label', 'Idioma do aplicativo');
    const badge = document.createElement('span'); badge.className = 'language-badge'; badge.dataset.noTranslate = '';
    const label = document.createElement('span'); label.className = 'language-current'; label.dataset.noTranslate = '';
    const arrow = document.createElement('span'); arrow.className = 'language-chevron'; arrow.setAttribute('aria-hidden','true'); const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); chevron.setAttribute('class', 'ic'); const use = document.createElementNS('http://www.w3.org/2000/svg', 'use'); use.setAttribute('href', '#i-chevron'); chevron.appendChild(use); arrow.appendChild(chevron);
    trigger.append(badge, label, arrow); select.after(trigger);
    const popup = document.createElement('dialog'); popup.className = 'language-menu'; popup.id = select.id + '-menu';
    popup.setAttribute('aria-label', 'Idioma do aplicativo');
    const list = document.createElement('div'); list.className = 'language-options'; list.setAttribute('role','listbox');
    list.setAttribute('aria-label', 'Idioma do aplicativo'); trigger.setAttribute('aria-controls', popup.id);
    const options = [];
    for (const option of select.options) {
      const row = document.createElement('button'); row.type = 'button'; row.className = 'language-option';
      row.setAttribute('role','option'); row.lang = option.value; row.dataset.value = option.value;
      const mark = document.createElement('span'); mark.className = 'language-badge'; mark.textContent = badges[option.value]; mark.dataset.noTranslate = '';
      const text = document.createElement('span'); text.className = 'language-option-text'; text.dataset.noTranslate = '';
      const name = document.createElement('strong'); name.textContent = option.text;
      const small = document.createElement('small'); small.textContent = option.value === 'pt-BR' ? subtitles[option.value] : option.value.toUpperCase();
      text.append(name, small);
      const check = document.createElement('span'); check.className = 'language-check'; check.textContent = '✓'; check.setAttribute('aria-hidden','true');
      row.append(mark, text, check);
      row.addEventListener('click', () => {
        select.value = option.value;
        select.dispatchEvent(new Event('change', {bubbles:true}));
        update(); popup.close();
      });
      list.appendChild(row); options.push(row);
    }
    popup.appendChild(list); document.body.appendChild(popup);
    function update() {
      const selected = select.selectedOptions[0];
      badge.textContent = badges[select.value] || 'A'; label.textContent = selected?.text || '';
      for (const option of options) {
        const current = option.dataset.value === select.value;
        option.setAttribute('aria-selected', String(current)); option.tabIndex = current ? 0 : -1;
      }
    }
    function position() {
      const rect = trigger.getBoundingClientRect(), margin = 12, gap = 8;
      const below = innerHeight - rect.bottom - gap - margin, above = rect.top - gap - margin;
      const height = Math.min(380, innerHeight - margin * 2, Math.max(above, below));
      popup.style.width = Math.min(Math.max(rect.width, 260), innerWidth - margin * 2) + 'px';
      popup.style.maxHeight = Math.max(100, height) + 'px';
      popup.style.left = Math.max(margin, Math.min(rect.left, innerWidth - parseFloat(popup.style.width) - margin)) + 'px';
      const actual = popup.getBoundingClientRect().height;
      popup.style.top = (below >= actual || below >= above ? rect.bottom + gap : Math.max(margin, rect.top - gap - actual)) + 'px';
    }
    trigger.addEventListener('click', () => {
      update(); popup.showModal(); position(); trigger.setAttribute('aria-expanded','true');
      (options.find(option => option.dataset.value === select.value) || options[0]).focus({preventScroll:true});
    });
    list.addEventListener('keydown', event => {
      if (!['ArrowDown','ArrowUp','Home','End'].includes(event.key)) return;
      event.preventDefault();
      const index = options.indexOf(document.activeElement);
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 :
        (index + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
      options[next].focus();
    });
    popup.addEventListener('cancel', event => {event.stopPropagation();});
    popup.addEventListener('click', event => {
      const rect = popup.getBoundingClientRect();
      if (event.target === popup && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) popup.close();
    });
    popup.addEventListener('close', () => {trigger.setAttribute('aria-expanded','false'); trigger.focus({preventScroll:true});});
    window.addEventListener('resize', () => {if (popup.open) position();});
    select.addEventListener('change', update);
    controls.set(select.id, {refresh:update}); update();
  }
  window.LanguagePicker = {mount, refresh};
})();
