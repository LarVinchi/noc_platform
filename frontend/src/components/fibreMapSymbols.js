export const COLORS = { live: '#35e0a1', down: '#ff5c5c', planned: '#7aa2ff', unknown: '#e8b84a' };
export const STATUS_LABEL = { live: 'Live', down: 'Down', planned: 'Planned', unknown: 'Not set' };
export const TYPE_LABEL = { cls: "Cable landing station", pop: "Point of presence", closure: "Splice closure", handhole: "Handhole", customer: "Customer site", fault: "Fault" };

export function nodeSvg(type, status) {
  const c = COLORS[status] || COLORS.unknown;
  switch (type) {
    case "pop":
      return `<svg viewBox="0 0 40 40" width="40" height="40"><rect x="4" y="4" width="32" height="32" rx="9" fill="#071820" stroke="#5cc8ff" stroke-width="2.5"/>
        <circle cx="20" cy="20" r="4" fill="#5cc8ff"/><circle cx="20" cy="20" r="9" fill="none" stroke="#5cc8ff" stroke-width="2" opacity=".7"/>
        <circle cx="20" cy="20" r="14" fill="none" stroke="#5cc8ff" stroke-width="1.5" opacity=".35"/></svg>`;
    case "cls":
      return `<svg viewBox="0 0 40 40" width="40" height="40"><path d="M20 3 35 11.5v17L20 37 5 28.5v-17Z" fill="#1d0b19" stroke="#ff7bd5" stroke-width="2.5"/>
        <path d="M11 17q4.5-4 9 0t9 0M11 23q4.5-4 9 0t9 0" fill="none" stroke="#ff7bd5" stroke-width="2.2" stroke-linecap="round"/></svg>`;
    case "closure":
      return `<svg viewBox="0 0 24 24" width="24" height="24"><circle cx="12" cy="12" r="9" fill="#071820" stroke="#e4edf1" stroke-width="2.5"/><circle cx="12" cy="12" r="4.5" fill="${c}"/></svg>`;
    case "handhole":
      return `<svg viewBox="0 0 16 16" width="16" height="16"><rect x="3" y="3" width="10" height="10" rx="2" fill="#071820" stroke="#9fb4bf" stroke-width="2"/><rect x="6" y="6" width="4" height="4" fill="${c}"/></svg>`;
    case "customer":
      return `<svg viewBox="0 0 28 28" width="28" height="28"><path d="M14 2 26 14 14 26 2 14Z" fill="#071820" stroke="#b69cff" stroke-width="2.5"/><circle cx="14" cy="14" r="4" fill="#b69cff"/></svg>`;
    case "fault":
      return `<div class="pulse-ring"></div><svg viewBox="0 0 30 30" width="30" height="30"><circle cx="15" cy="15" r="12" fill="#2a0c10" stroke="#ff5c5c" stroke-width="2.5"/>
        <path d="M10 10 20 20M20 10 10 20" stroke="#ff5c5c" stroke-width="3" stroke-linecap="round"/></svg>`;
    default:
      return `<svg viewBox="0 0 20 20" width="20" height="20"><circle cx="10" cy="10" r="7" fill="#071820" stroke="${c}" stroke-width="3"/></svg>`;
  }
}

