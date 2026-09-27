// Apply the saved theme before paint; blocked storage must not break the page.
try {
  // The storage key stays stable across the publication's rename.
  const stored = localStorage.getItem('defter.theme');
  const theme = stored === 'light' || stored === 'dark' ? stored : (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.dataset.theme = theme;
} catch {
  document.documentElement.dataset.theme = 'light';
}
