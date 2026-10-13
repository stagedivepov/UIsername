(() => {
  'use strict';
  const dialog = document.getElementById('cancel-confirm-dialog');
  let waiting = null;
  dialog.querySelector('[data-keep-running]').addEventListener('click', () => dialog.close('keep'));
  dialog.querySelector('[data-confirm-cancel]').addEventListener('click', () => dialog.close('confirm'));
  dialog.addEventListener('close', () => {
    const resolve = waiting; waiting = null;
    if (resolve) resolve(dialog.returnValue === 'confirm');
  });
  window.ConfirmAction = {
    ask(title = 'Cancelar execução?') {
      if (waiting) return Promise.resolve(false);
      document.getElementById('cancel-confirm-title').textContent = title;
      dialog.returnValue = '';
      return new Promise(resolve => {
        waiting = resolve;
        try {dialog.showModal();} catch (_) {waiting = null; resolve(false);}
      });
    },
    get open() {return dialog.open;}
  };
})();
