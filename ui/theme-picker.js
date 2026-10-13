window.THEME_DEFINITIONS = [{"id": "dark", "name": "Escuro", "bg": "#101217", "surface": "#15181f", "text": "#edf0f7", "accent": "#b68cff"}, {"id": "light", "name": "Claro", "bg": "#eef0f6", "surface": "#ffffff", "text": "#26344f", "accent": "#6936ba"}, {"id": "sky", "name": "Céu estrelado", "bg": "#080f26", "surface": "rgba(14,24,49,.86)", "text": "#eef6ff", "accent": "#adbdff"}, {"id": "dracula", "name": "Dracula", "bg": "#282a36", "surface": "#21222c", "text": "#f8f8f2", "accent": "#bd93f9"}, {"id": "nord", "name": "Nord", "bg": "#2e3440", "surface": "#3b4252", "text": "#eceff4", "accent": "#88c0d0"}, {"id": "catppuccin", "name": "Catppuccin Mocha", "bg": "#1e1e2e", "surface": "#181825", "text": "#cdd6f4", "accent": "#cba6f7"}, {"id": "tokyo-night", "name": "Tokyo Night", "bg": "#1a1b26", "surface": "#16161e", "text": "#c0caf5", "accent": "#7aa2f7"}, {"id": "rose-pine", "name": "Rosé Pine", "bg": "#191724", "surface": "#1f1d2e", "text": "#e0def4", "accent": "#ebbcba"}, {"id": "system", "name": "Seguir o sistema", "bg": "#edf0f7", "surface": "#73758b", "text": "#cdd6f4", "accent": "#b68cff"}];
(() => {
  'use strict';
  let select, trigger, title, swatch, popup, cards = [];
  const defs = window.THEME_DEFINITIONS;
  function colors(element, theme) {for (const key of ['bg','surface','text','accent']) element.style.setProperty('--preview-' + key, theme[key]);}
  function refresh() {
    if (!select) return;
    const theme = defs.find(item => item.id === select.value) || defs[0];
    title.textContent = theme.name; colors(swatch, theme);
    for (const card of cards) {const active = card.dataset.themeId === theme.id; card.setAttribute('aria-selected', String(active)); card.tabIndex = active ? 0 : -1;}
  }
  function mount(control) {
    if (select) return;
    select = control; select.hidden = true; select.replaceChildren();
    for (const theme of defs) {const option = document.createElement('option'); option.value = theme.id; option.textContent = theme.name; select.appendChild(option);}
    trigger = document.createElement('button'); trigger.type = 'button'; trigger.className = 'theme-trigger';
    trigger.id = 'theme-picker-open'; trigger.setAttribute('aria-label', 'Escolha um tema'); trigger.setAttribute('aria-haspopup','listbox'); trigger.setAttribute('aria-expanded','false');
    swatch = document.createElement('span'); swatch.className = 'theme-trigger-swatch'; swatch.setAttribute('aria-hidden','true');
    title = document.createElement('span'); title.className = 'theme-trigger-name';
    const arrow = document.createElement('span'); arrow.className = 'theme-trigger-arrow'; const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); chevron.setAttribute('class', 'ic'); const use = document.createElementNS('http://www.w3.org/2000/svg', 'use'); use.setAttribute('href', '#i-chevron'); chevron.appendChild(use); arrow.appendChild(chevron); arrow.setAttribute('aria-hidden','true');
    trigger.append(swatch,title,arrow); select.after(trigger);
    popup = document.createElement('dialog'); popup.id = 'theme-gallery'; popup.className = 'theme-gallery'; popup.setAttribute('aria-labelledby','theme-gallery-title');
    trigger.setAttribute('aria-controls',popup.id);
    const header = document.createElement('header'); header.className = 'theme-gallery-header';
    const copy = document.createElement('div'), heading = document.createElement('h2'), hint = document.createElement('p');
    heading.id = 'theme-gallery-title'; heading.textContent = 'Escolha um tema'; hint.textContent = 'Prévia instantânea · Salvo automaticamente'; copy.append(heading,hint);
    const close = document.createElement('button'); close.type = 'button'; close.className = 'theme-gallery-close'; close.id = 'theme-gallery-close'; close.setAttribute('aria-label','Fechar temas');
    close.innerHTML = '<svg class="ic" aria-hidden="true"><use href="#i-close"/></svg>';
    close.addEventListener('click', () => popup.close()); header.append(copy,close);
    const grid = document.createElement('div'); grid.className = 'theme-grid'; grid.setAttribute('role','listbox'); grid.setAttribute('aria-label','Temas');
    for (const theme of defs) {
      const card = document.createElement('button'); card.type = 'button'; card.className = 'theme-card'; card.dataset.themeId = theme.id; card.setAttribute('role','option');
      const preview = document.createElement('span'); preview.className = 'theme-preview'; preview.dataset.palette = theme.id; preview.setAttribute('aria-hidden','true'); colors(preview,theme);
      for (const part of ['top','side','lines','button']) {const mini = document.createElement('i'); mini.className = 'theme-mini-' + part; preview.appendChild(mini);}
      const label = document.createElement('span'); label.className = 'theme-card-label'; label.textContent = theme.name;
      const check = document.createElement('span'); check.className = 'theme-card-check'; check.textContent = '✓'; check.setAttribute('aria-hidden','true');
      card.append(preview,label,check); card.addEventListener('click', () => {select.value = theme.id; select.dispatchEvent(new Event('change',{bubbles:true})); refresh();});
      cards.push(card); grid.appendChild(card);
    }
    popup.append(header,grid); document.body.appendChild(popup);
    trigger.addEventListener('click', () => {refresh(); popup.showModal(); trigger.setAttribute('aria-expanded','true'); (cards.find(card => card.dataset.themeId === select.value) || cards[0]).focus({preventScroll:true});});
    grid.addEventListener('keydown', event => {
      if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key)) return;
      event.preventDefault(); const index = cards.indexOf(document.activeElement), cols = getComputedStyle(grid).gridTemplateColumns.split(' ').length;
      const delta = event.key === 'ArrowDown' ? cols : event.key === 'ArrowUp' ? -cols : event.key === 'ArrowLeft' ? -1 : 1;
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? cards.length - 1 : (index + delta + cards.length) % cards.length; cards[next].focus();
    });
    popup.addEventListener('cancel', event => event.stopPropagation());
    popup.addEventListener('click', event => {const rect = popup.getBoundingClientRect(); if (event.target === popup && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) popup.close();});
    popup.addEventListener('close', () => {trigger.setAttribute('aria-expanded','false'); trigger.focus({preventScroll:true});});
    select.addEventListener('change', refresh); refresh();
  }
  window.ThemePicker = {mount, refresh};
})();
