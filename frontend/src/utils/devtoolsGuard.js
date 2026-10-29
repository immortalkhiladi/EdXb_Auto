// UI-level DETERRENT only: discourages casual inspection by swallowing common DevTools / view-source shortcuts
// and the right-click menu. It does NOT protect anything (browsers can always inspect what they receive);
// real security is enforced by the Django backend (authentication, authorisation, validation, secrets).

/** True when the keyboard event is one of the shortcuts we discourage. Pure function (unit-tested). */
export function isBlockedShortcut(event, isMac = false) {
  const key = String(event.key || '').toUpperCase();
  const code = event.code || '';
  const ctrlOrCmd = !!event.ctrlKey || (isMac && !!event.metaKey);
  const shiftOrAlt = !!event.shiftKey || (isMac && !!event.altKey);

  const f12 = event.key === 'F12' || code === 'F12';
  const devtools = ctrlOrCmd && shiftOrAlt && ['I', 'J', 'C'].includes(key); // Ctrl+Shift+I / J / C (Cmd+Option on Mac)
  const viewSource = (!!event.ctrlKey && key === 'U') || (isMac && !!event.metaKey && !!event.altKey && key === 'U'); // Ctrl+U
  const firefoxConsole = !!event.ctrlKey && !!event.shiftKey && key === 'K'; // Ctrl+Shift+K
  return f12 || devtools || viewSource || firefoxConsole;
}
