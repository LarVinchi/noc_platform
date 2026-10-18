import { createElement } from 'react';
import { CircleAlert, CircleCheck, Info, RefreshCw } from 'lucide-react';

export function PageHeader({ eyebrow, title, description, children }) {
  return <header className="page-header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1><p>{description}</p></div>{children && <div className="page-actions">{children}</div>}</header>;
}
export function RefreshButton({ busy, onClick }) { return <button className="response-button" disabled={busy} onClick={onClick}><RefreshCw size={15} className={busy ? 'is-refreshing' : ''} />{busy ? 'Refreshing…' : 'Refresh'}</button>; }
export function StateBadge({ tone = 'neutral', children }) { return <span className={`state-badge state-badge--${tone}`}>{createElement(tone === 'success' ? CircleCheck : tone === 'danger' || tone === 'warning' ? CircleAlert : Info, { size: 12 })}{children}</span>; }
export function MetricPanel({ label, value, description, icon, tone = 'accent' }) { return <section className={`metric-panel metric-panel--${tone}`}><div><h2>{label}</h2>{createElement(icon, { size: 18 })}</div><strong>{value}</strong><p>{description}</p></section>; }
export function EmptyState({ title, children, icon = Info }) { return <div className="workspace-empty">{createElement(icon, { size: 25 })}<h3>{title}</h3><p>{children}</p></div>; }
export function LoadingRows({ rows = 4 }) { return <div className="loading-rows" role="status" aria-label="Loading data">{Array.from({ length: rows }, (_, i) => <div key={i}><span /><span /><span /></div>)}</div>; }
export function TableRegion({ label, children }) { return <div className="workspace-table-scroll" role="region" aria-label={label} tabIndex={0}>{children}</div>; }
export function FilterTabs({ label, options, value, onChange }) { return <div className="filter-tabs" role="group" aria-label={label}>{options.map(option => <button key={option.value} aria-pressed={value === option.value} onClick={() => onChange(option.value)}>{option.label}</button>)}</div>; }
