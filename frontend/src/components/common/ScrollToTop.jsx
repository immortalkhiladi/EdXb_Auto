import { useLayoutEffect } from 'react';
import { useLocation } from 'react-router-dom';

// Resets scroll to the top on every route change (unless navigating to a #hash anchor).
export default function ScrollToTop() {
  const { pathname, hash } = useLocation();

  useLayoutEffect(() => {
    if (hash) return;
    window.scrollTo(0, 0);
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, [pathname, hash]);

  return null;
}
