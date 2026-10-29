import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext.jsx';

export default function ThemeToggle({ className = '' }) {
  const { isDark, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      type="button"
      title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
      aria-label="Toggle theme"
      className={`relative inline-flex items-center justify-center p-2.5 rounded-xl text-navy-100 hover:text-white hover:bg-white/10 border border-white/15 transition-colors focus:outline-none focus:ring-2 focus:ring-turquoise-400/60 cursor-pointer ${className}`}
    >
      {isDark ? (
        <Sun className="h-4 w-4 text-amber-400 hover:rotate-45 transition-transform duration-200" />
      ) : (
        <Moon className="h-4 w-4 text-turquoise-300 hover:-rotate-12 transition-transform duration-200" />
      )}
    </button>
  );
}
