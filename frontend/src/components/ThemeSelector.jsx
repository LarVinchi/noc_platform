import { createElement, useSyncExternalStore } from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';

const subscribe = listener => { window.addEventListener('noc-theme-change', listener); window.addEventListener('storage', listener); return () => { window.removeEventListener('noc-theme-change', listener); window.removeEventListener('storage', listener); }; };
const snapshot = () => document.documentElement.dataset.preference || 'system';
export default function ThemeSelector() {
  const preference = useSyncExternalStore(subscribe, snapshot, () => 'system');
  return <div className="theme-selector" role="group" aria-label="Appearance">
    {[[ 'light', Sun, 'Light' ], [ 'dark', Moon, 'Dark' ], [ 'system', Monitor, 'System' ]].map(([value, Icon, label]) => <button key={value} type="button" aria-label={`${label} theme`} aria-pressed={preference === value} title={`${label} theme`} onClick={() => window.nocTheme.set(value)}>{createElement(Icon, { size: 15 })}<span>{label}</span></button>)}
  </div>;
}
