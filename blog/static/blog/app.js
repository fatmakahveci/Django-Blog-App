(() => {
  'use strict';
  // Keep existing readers' saved IDs when the publication is renamed.
  const key = 'defter.saved';
  const toast = document.getElementById('toast');
  let toastTimer;
  function announce(message) {
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 3500);
  }
  window.addEventListener('folio:announce', event => announce(event.detail));
  function readSaved() {
    try {
      const value = JSON.parse(localStorage.getItem(key) || '[]');
      return Array.isArray(value) ? [...new Set(value.filter(id => /^\d{1,10}$/.test(String(id))).map(String))].slice(0, 100) : [];
    } catch { return []; }
  }
  function syncSaved() {
    const ids = readSaved();
    document.querySelectorAll('[data-save-id]').forEach(button => {
      const saved = ids.includes(button.dataset.saveId);
      button.setAttribute('aria-pressed', String(saved));
      const label = button.querySelector('[data-save-label]') || button;
      label.textContent = saved ? 'Saved' : 'Save';
      button.setAttribute('aria-label', `${saved ? 'Saved' : 'Save'}${button.dataset.saveTitle ? `: ${button.dataset.saveTitle}` : ''}`);
      button.title = saved ? 'Remove from reading list' : 'Save to reading list';
    });
    document.querySelectorAll('[data-saved-count]').forEach(counter => { counter.textContent = ids.length; });
    document.querySelectorAll('[data-reading-list-link]').forEach(link => {
      const url = new URL(link.href);
      if (ids.length) url.searchParams.set('ids', ids.join(',')); else url.searchParams.delete('ids');
      link.href = url.pathname + url.search;
    });
    return ids;
  }
  document.querySelectorAll('.js-control').forEach(button => { button.hidden = false; });
  document.querySelectorAll('[data-save-id]').forEach(button => {
    button.addEventListener('click', () => {
      const ids = readSaved();
      const id = button.dataset.saveId;
      const alreadySaved = ids.includes(id);
      if (!alreadySaved && ids.length >= 100) { announce('You can save up to 100 articles in your reading list.'); return; }
      const updated = alreadySaved ? ids.filter(value => value !== id) : [...ids, id];
      try { localStorage.setItem(key, JSON.stringify(updated)); }
      catch { announce('Your browser cannot save this list. Please check your privacy settings.'); return; }
      syncSaved();
      announce(alreadySaved ? 'Article removed from your reading list.' : 'Article added to your reading list.');
      if (document.body.dataset.readingList === 'true') refreshReadingList(updated);
    });
  });
  function refreshReadingList(ids) {
    const url = new URL(location.href);
    const wanted = ids.join(',');
    if ((url.searchParams.get('ids') || '') !== wanted) {
      if (wanted) url.searchParams.set('ids', wanted); else url.searchParams.delete('ids');
      url.searchParams.delete('page');
      location.replace(url.pathname + url.search);
    }
  }
  const saved = syncSaved();
  if (document.body.dataset.readingList === 'true') refreshReadingList(saved);
  window.addEventListener('storage', event => {
    // A null key means another tab cleared storage entirely.
    if (event.key === key || event.key === null) {
      const ids = syncSaved();
      if (document.body.dataset.readingList === 'true') refreshReadingList(ids);
    }
  });
  const search = document.querySelector('input[type="search"]');
  document.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.isComposing || event.ctrlKey || event.metaKey || event.altKey) return;
    const editing = event.target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"])');
    if (event.key === '/' && search && !editing) {
      event.preventDefault();
      search.focus();
    } else if (event.key === 'Escape' && event.target === search) {
      search.blur();
    }
  });
  const themeButton = document.querySelector('[data-theme-toggle]');
  function updateThemeButton() {
    const dark = document.documentElement.dataset.theme === 'dark';
    themeButton.setAttribute('aria-pressed', String(dark));
    themeButton.setAttribute('aria-label', dark ? 'Switch to light theme' : 'Switch to dark theme');
  }
  updateThemeButton();
  themeButton.addEventListener('click', () => {
    const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('defter.theme', theme); } catch { /* Theme still works for this visit. */ }
    updateThemeButton();
  });
  document.querySelector('[data-share]')?.addEventListener('click', async () => {
    const url = document.querySelector('link[rel="canonical"]')?.href || location.href.split('#')[0];
    try {
      await navigator.clipboard.writeText(url);
      announce('Article link copied.');
    } catch {
      announce('We could not copy the link. You can copy it from your browser address bar.');
    }
  });
  const article = document.querySelector('[data-article-body]');
  const progress = document.querySelector('.reading-progress');
  if (article && progress) {
    progress.hidden = false;
    let queued = false;
    function updateProgress() {
      const box = article.getBoundingClientRect();
      const height = Math.max(1, box.height - innerHeight * 0.5);
      const percent = Math.min(100, Math.max(0, (innerHeight * 0.3 - box.top) / height * 100));
      progress.firstElementChild.style.width = `${percent}%`;
      progress.setAttribute('aria-valuenow', String(Math.round(percent)));
      window.dispatchEvent(new CustomEvent('folio:reading-progress', { detail: percent }));
      queued = false;
    }
    function queueProgress() { if (!queued) { queued = true; requestAnimationFrame(updateProgress); } }
    addEventListener('scroll', queueProgress, { passive: true });
    addEventListener('resize', queueProgress);
    updateProgress();
  }
})();
