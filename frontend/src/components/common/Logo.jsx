import { Link } from 'react-router-dom';

// EDGAR Agents LLC wordmark. No official logo file is included in the repository: this is a typographic mark
// (an "EA" monogram tile + the company name). Drop the official SVG into src/assets and render it here when available.
export default function Logo({ size = 'default', showTagline = false, to = null, className = '' }) {
  const isLarge = size === 'large';
  const isSmall = size === 'small';
  const body = (
    <span className={`inline-flex items-center gap-2.5 select-none ${className}`}>
      <span
        aria-hidden="true"
        className={`ea-primary rounded-md font-black tracking-tight leading-none flex items-center justify-center ${
          isLarge ? 'h-10 w-10 text-base' : isSmall ? 'h-7 w-7 text-[11px]' : 'h-8 w-8 text-xs'
        }`}
      >
        EA
      </span>
      <span className="flex flex-col leading-none">
        <span className={`font-extrabold tracking-tight text-slate-950 dark:text-white ${isLarge ? 'text-lg' : isSmall ? 'text-xs' : 'text-sm'}`}>
          EDGAR Agents <span className="font-semibold text-slate-500 dark:text-slate-400">LLC</span>
        </span>
        {showTagline && (
          <span className="mt-1 text-[10px] font-semibold tracking-wider uppercase text-slate-500 dark:text-slate-400">
            File with confidence
          </span>
        )}
      </span>
    </span>
  );
  return to ? <Link to={to} aria-label="EDGAR Agents LLC">{body}</Link> : body;
}
