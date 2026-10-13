(() => {
  'use strict';
  let native = false, busy = false, fullscreen = false;
  const button = document.getElementById('window-fullscreen');
  function sync(state) {
    fullscreen = state.fullscreen;
    button.setAttribute('aria-label', fullscreen ? 'Sair da tela cheia' : 'Tela cheia');
    button.setAttribute('aria-pressed', String(fullscreen));
    document.body.classList.toggle('fullscreen', fullscreen);
    if (state.maximized !== undefined) {
      document.getElementById('window-maximize').setAttribute('aria-label', state.maximized ? 'Restaurar janela' : 'Maximizar');
      document.body.classList.toggle('maximized', state.maximized);
      document.getElementById('window-maximize-icon').setAttribute('href', state.maximized ? '#i-restore' : '#i-maximize');
    }
  }
  async function toggleFullscreen() {
    if (busy) return;
    busy = true;
    try {
      if (native) sync(await window.pywebview.api.fullscreen());
      else if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch (_) {button.setAttribute('title', 'Use F11 para tela cheia');}
    finally {busy = false;}
  }
  window.addEventListener('pywebviewready', async () => {
    native = true; document.body.classList.add('native-window');
    for (const control of document.querySelectorAll('.native-control')) control.hidden = false;
    sync(await window.pywebview.api.state());
  });
  document.addEventListener('fullscreenchange', () => {if (!native) sync({fullscreen: !!document.fullscreenElement});});
  document.addEventListener('keydown', event => {
    if (event.key === 'F11') {event.preventDefault(); if (!event.repeat) void toggleFullscreen();}
    if (event.key === 'Escape' && native && fullscreen && !Preferences.modalOpen) {event.preventDefault(); void toggleFullscreen();}
  }, true);
  const grip = document.getElementById('window-resize');
  let drag = null, pendingSize = null, resizing = false;
  async function resize() {
    if (resizing) return;
    resizing = true;
    try {
      while (pendingSize) {
        const size = pendingSize; pendingSize = null;
        await window.pywebview.api.resize(size.width, size.height);
      }
    } finally {resizing = false;}
  }
  grip.addEventListener('pointerdown', event => {
    if (!native || fullscreen || event.button !== 0) return;
    event.preventDefault(); grip.setPointerCapture(event.pointerId);
    drag = {x: event.clientX, y: event.clientY, width: innerWidth, height: innerHeight};
  });
  grip.addEventListener('pointermove', event => {
    if (!drag) return;
    pendingSize = {width: Math.round(drag.width + event.clientX - drag.x), height: Math.round(drag.height + event.clientY - drag.y)};
    void resize();
  });
  grip.addEventListener('pointerup', () => {drag = null;});
  grip.addEventListener('pointercancel', () => {drag = null;});
  grip.addEventListener('keydown', event => {
    const moves = {ArrowRight: [32,0], ArrowLeft: [-32,0], ArrowDown: [0,32], ArrowUp: [0,-32]};
    if (!native || !moves[event.key]) return;
    event.preventDefault();
    pendingSize = {width: innerWidth + moves[event.key][0], height: innerHeight + moves[event.key][1]}; void resize();
  });
  button.addEventListener('click', toggleFullscreen);
  document.getElementById('window-minimize').addEventListener('click', () => window.pywebview.api.minimize());
  async function maximize() {if (native && !fullscreen) sync(await window.pywebview.api.maximize());}
  document.getElementById('window-maximize').addEventListener('click', maximize);
  document.getElementById('window-drag').addEventListener('dblclick', maximize);
  document.getElementById('window-close').addEventListener('click', async () => {
    if (await Preferences.flush()) await window.pywebview.api.close();
    else Preferences.open();
  });
})();
