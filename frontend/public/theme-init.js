(function () {
  try {
    var theme = localStorage.getItem('edgar-agents-theme') || 'light';
    var root = document.documentElement;
    root.classList.toggle('dark', theme === 'dark');
    root.classList.toggle('light', theme !== 'dark');
  } catch (e) {}
})();
