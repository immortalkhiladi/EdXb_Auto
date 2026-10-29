import { useEffect } from 'react';
import { isBlockedShortcut } from '../utils/devtoolsGuard.js';

/**
 * Applies the UI-level deterrents on every page: F12, Ctrl+Shift+I/J/C, Ctrl+U (Cmd+Option on Mac) and the
 * right-click context menu. The tool pages (separate sandboxed documents) get the same handlers from the
 * server-injected bridge script.
 *
 * SECURITY NOTE: this is only a deterrent. Anyone can still inspect the frontend code and network traffic.
 * Real protection lives on the Django backend (authentication, roles, validation, secrets, private storage).
 */
export function useDevToolsProtection({ disableContextMenu = true, disableShortcuts = true, enabled = true } = {}) {
  useEffect(() => {
    if (!enabled) return undefined;
    const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform || '');

    const onKeyDown = (event) => {
      if (disableShortcuts && isBlockedShortcut(event, isMac)) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    const onContextMenu = (event) => {
      if (disableContextMenu) event.preventDefault();
    };

    document.addEventListener('keydown', onKeyDown, true);
    document.addEventListener('contextmenu', onContextMenu, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      document.removeEventListener('contextmenu', onContextMenu, true);
    };
  }, [enabled, disableContextMenu, disableShortcuts]);
}

export default useDevToolsProtection;
