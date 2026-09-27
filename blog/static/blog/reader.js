(() => {
  'use strict';
  const keys = { topics: 'folio.topics', history: 'folio.history', preferences: 'folio.reader' };
  const announce = message => window.dispatchEvent(new CustomEvent('folio:announce', { detail: message }));
  const validId = value => /^\d{1,10}$/.test(String(value));
  function read(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
  }
  function topicIds() {
    const value = read(keys.topics, []);
    return Array.isArray(value) ? [...new Set(value.filter(validId).map(String))].slice(0, 20) : [];
  }
  function history() {
    const value = read(keys.history, []);
    if (!Array.isArray(value)) return [];
    const seen = new Set();
    return value.filter(entry => {
      if (!entry || !validId(entry.id) || seen.has(String(entry.id)) || !Number.isFinite(entry.progress)) return false;
      seen.add(String(entry.id)); return true;
    }).slice(0, 20).map(entry => ({ id: String(entry.id), progress: Math.max(0, Math.min(100, entry.progress)) }));
  }
  function personalLinks(selector, parameter, ids) {
    document.querySelectorAll(selector).forEach(link => {
      const url = new URL(link.href);
      if (ids.length) url.searchParams.set(parameter, ids.join(',')); else url.searchParams.delete(parameter);
      link.href = url.pathname + url.search;
    });
  }
  function refreshPersonal(parameter, ids) {
    const url = new URL(location.href);
    const value = ids.join(',');
    if ((url.searchParams.get(parameter) || '') === value) return;
    if (value) url.searchParams.set(parameter, value); else url.searchParams.delete(parameter);
    url.searchParams.delete('page');
    location.replace(url.pathname + url.search);
  }
  function syncPersonal() {
    const topics = topicIds();
    const recent = history();
    document.querySelectorAll('[data-follow-topic]').forEach(button => {
      const followed = topics.includes(button.dataset.followTopic);
      button.hidden = false;
      button.setAttribute('aria-pressed', String(followed));
      button.textContent = `${followed ? 'Following' : 'Follow'} ${button.dataset.topicName}`;
    });
    personalLinks('[data-for-you-link]', 'topics', topics);
    personalLinks('[data-history-link]', 'ids', recent.map(entry => entry.id));
    if (document.body.dataset.forYou === 'true') refreshPersonal('topics', topics);
    if (document.body.dataset.history === 'true') {
      refreshPersonal('ids', recent.map(entry => entry.id));
      document.querySelectorAll('[data-resume-card]').forEach(link => {
        const item = recent.find(entry => entry.id === link.dataset.resumeCard);
        const progress = Math.round(item?.progress || 0);
        link.textContent = progress >= 98 ? 'Finished · Read again ↗' : progress > 0 ? `Resume at ${progress}% ↗` : 'Start reading ↗';
      });
    }
  }
  document.querySelectorAll('[data-follow-topic]').forEach(button => {
    button.addEventListener('click', () => {
      const ids = topicIds();
      const id = button.dataset.followTopic;
      const followed = ids.includes(id);
      if (!followed && ids.length >= 20) { announce('You can follow up to 20 topics. Unfollow one to make room.'); return; }
      if (!write(keys.topics, followed ? ids.filter(value => value !== id) : [...ids, id])) {
        announce('Your browser could not save your topics. Please check your privacy settings.'); return;
      }
      syncPersonal();
      announce(followed ? `Unfollowed ${button.dataset.topicName}.` : `${button.dataset.topicName} is now in your For you feed.`);
    });
  });
  const clearHistory = document.querySelector('[data-clear-history]');
  if (clearHistory) {
    clearHistory.hidden = false;
    clearHistory.addEventListener('click', () => {
      if (!write(keys.history, [])) { announce('Your browser could not clear this history.'); return; }
      syncPersonal(); announce('Reading history cleared.');
    });
  }
  syncPersonal();
  addEventListener('storage', event => {
    if ([keys.topics, keys.history, null].includes(event.key)) syncPersonal();
  });

  const controls = document.querySelector('[data-reader-controls]');
  const text = document.querySelector('[data-article-body]');
  if (!controls || !text) return;
  controls.hidden = false;
  const size = controls.querySelector('[data-reading-size]');
  const focus = controls.querySelector('[data-focus-toggle]');
  const savedPreferences = read(keys.preferences, {});
  const preferences = {
    size: ['standard', 'large', 'largest'].includes(savedPreferences?.size) ? savedPreferences.size : 'standard',
    focus: savedPreferences?.focus === true,
  };
  function applyPreferences() {
    document.body.dataset.readingSize = preferences.size;
    document.body.dataset.focus = String(preferences.focus);
    size.value = preferences.size;
    focus.setAttribute('aria-pressed', String(preferences.focus));
    focus.textContent = preferences.focus ? 'Exit focus mode' : 'Focus mode';
    dispatchEvent(new Event('resize'));
  }
  function savePreferences() {
    applyPreferences();
    if (!write(keys.preferences, preferences)) announce('Your reading preference applies to this visit. Browser storage is unavailable.');
  }
  size.addEventListener('change', () => { preferences.size = size.value; savePreferences(); });
  focus.addEventListener('click', () => { preferences.focus = !preferences.focus; savePreferences(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && preferences.focus) { preferences.focus = false; savePreferences(); }
  });
  applyPreferences();

  const postId = document.querySelector('[data-reader-post]')?.dataset.readerPost;
  if (postId) {
    const previous = history().find(item => item.id === postId);
    const resume = controls.querySelector('[data-resume-reading]');
    let progress = previous?.progress || 0;
    let lastWrite = 0;
    let historyEnabled = true;
    function remember() {
      if (!historyEnabled) return;
      write(keys.history, [{ id: postId, progress }, ...history().filter(item => item.id !== postId)].slice(0, 20));
      lastWrite = Date.now();
      personalLinks('[data-history-link]', 'ids', history().map(entry => entry.id));
    }
    remember();
    addEventListener('folio:reading-progress', event => {
      progress = Math.max(progress, event.detail);
      if (Date.now() - lastWrite > 2000) remember();
    });
    addEventListener('pagehide', remember);
    // Clearing history in another tab must not immediately recreate old entries.
    addEventListener('storage', event => {
      if (event.key === null || (event.key === keys.history && !history().some(item => item.id === postId))) historyEnabled = false;
    });
    async function resumeReading() {
      await document.fonts?.ready;
      const top = scrollY + text.getBoundingClientRect().top;
      const height = Math.max(1, text.getBoundingClientRect().height - innerHeight * 0.5);
      scrollTo({ top: Math.max(0, top - innerHeight * 0.3 + previous.progress / 100 * height), behavior: 'instant' });
      announce('Your reading place has been restored.');
    }
    if (previous && previous.progress > 3 && previous.progress < 98) {
      resume.hidden = false;
      resume.textContent = `Resume at ${Math.round(previous.progress)}%`;
      resume.addEventListener('click', resumeReading);
      if (new URLSearchParams(location.search).get('resume') === '1') resumeReading();
    }
  }

  const audioControls = controls.querySelector('[data-listen-controls]');
  const listen = controls.querySelector('[data-listen]');
  const stop = controls.querySelector('[data-listen-stop]');
  const speed = controls.querySelector('[data-listen-speed]');
  const status = controls.querySelector('[data-listen-status]');
  const speech = window.speechSynthesis;
  if (!speech || !window.SpeechSynthesisUtterance) {
    status.textContent = 'Read-aloud is unavailable in this browser.'; return;
  }
  let voice;
  let phase = 'idle';
  let chunks = [];
  let index = 0;
  let generation = 0;
  let utterance;
  function availableVoices() {
    voice = speech.getVoices().find(item => item.localService && /^en(?:[-_]|$)/i.test(item.lang));
    audioControls.hidden = !voice;
    if (phase === 'idle') status.textContent = voice ? 'Listen using an English voice on this device.' : 'Read-aloud needs an English voice installed on this device.';
  }
  function finish(message) {
    generation += 1;
    phase = 'idle';
    speech.cancel();
    utterance = null;
    listen.textContent = 'Listen to article';
    stop.hidden = true;
    status.textContent = message;
  }
  function speakChunk() {
    if (index >= chunks.length) { finish('Finished reading.'); return; }
    const current = generation;
    // Short chunks avoid long-utterance limits and keep stop/speed controls responsive.
    utterance = new SpeechSynthesisUtterance(chunks[index]);
    utterance.voice = voice;
    utterance.lang = voice.lang;
    utterance.rate = Number(speed.value);
    utterance.onend = () => { if (current === generation) { index += 1; speakChunk(); } };
    utterance.onerror = () => { if (current === generation) finish('Playback could not continue. Try listening again.'); };
    speech.speak(utterance);
  }
  listen.addEventListener('click', () => {
    if (phase === 'playing') {
      speech.pause(); phase = 'paused'; listen.textContent = 'Resume audio'; status.textContent = 'Audio paused.';
    } else if (phase === 'paused') {
      speech.resume(); phase = 'playing'; listen.textContent = 'Pause audio'; status.textContent = 'Reading aloud.';
    } else if (voice) {
      chunks = (text.innerText.match(/[\s\S]{1,220}(?:\s|$)|[\s\S]{1,220}/g) || []).map(chunk => chunk.trim()).filter(Boolean);
      index = 0; generation += 1; phase = 'playing';
      listen.textContent = 'Pause audio'; stop.hidden = false; status.textContent = 'Reading aloud.';
      speech.cancel();
      if (speech.paused) speech.resume();
      speakChunk();
    }
  });
  stop.addEventListener('click', () => finish('Playback stopped.'));
  speed.addEventListener('change', () => {
    if (phase !== 'idle') {
      generation += 1; speech.cancel();
      if (speech.paused) speech.resume();
      phase = 'playing'; listen.textContent = 'Pause audio';
      status.textContent = 'Reading aloud.'; speakChunk();
    }
  });
  addEventListener('pagehide', () => finish('Playback stopped.'));
  speech.addEventListener('voiceschanged', availableVoices);
  availableVoices();
})();
