import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext.jsx';
import { AuthProvider } from './context/AuthContext.jsx';
import AppRoutes from './routes/AppRoutes.jsx';
import ScrollToTop from './components/common/ScrollToTop.jsx';
import { useDevToolsProtection } from './hooks/useDevToolsProtection.js';

export default function App() {
  // Global frontend deterrent against casual shortcut inspection & right-click
  // On for every page (login, reset password, dashboard, documents, admin, settings, 404) in production AND `npm run dev`.
  // Developers who need DevTools locally can set VITE_DEVTOOLS_DETERRENT=false. Deterrent only - see utils/devtoolsGuard.js.
  useDevToolsProtection({
    disableContextMenu: true,
    disableShortcuts: true,
    enabled: import.meta.env.VITE_DEVTOOLS_DETERRENT !== 'false'
  });

  return (
    <BrowserRouter>
      <ScrollToTop />
      <ThemeProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
