import { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

function shiftEnergyDay(day, count) {
  const value = new Date(day + 'T12:00:00Z');
  value.setUTCDate(value.getUTCDate() + count);
  return value.toISOString().slice(0, 10);
}

export default function EnergyDatePicker({ value, onChange, today, weekly = false }) {
  const [draft, setDraft] = useState(value);
  const monday = day => { const date = new Date(day + 'T12:00:00Z'); return shiftEnergyDay(day, -(date.getUTCDay() + 6) % 7); };
  const step = weekly ? 7 : 1, latest = weekly ? monday(today) : today;
  const commit = day => onChange(weekly ? monday(day) : day);
  const weekLabel = day => new Intl.DateTimeFormat('en-GB', { day:'numeric',month:'short',year:'numeric',timeZone:'Africa/Lagos' }).format(new Date(day+'T12:00:00Z'));
  return <div className="energy-date-picker"><button className="response-button" aria-label={weekly ? 'Previous week' : 'Previous day'} disabled={value <= (weekly ? '2000-01-03' : '2000-01-02')} onClick={() => commit(shiftEnergyDay(value,-step))}><ChevronLeft size={16}/></button>
    <form onSubmit={event => { event.preventDefault(); if (draft) commit(draft); }}><label>{weekly ? 'Choose any day in the week (WAT)' : 'Day (WAT)'}<input aria-label={weekly ? 'Week date' : 'Report date'} type="date" min={weekly?'2000-01-03':'2000-01-02'} max={today} required value={draft} onChange={event => setDraft(event.target.value)}/></label><button className="response-button" type="submit">Apply</button></form>
    <button className="response-button" aria-label={weekly ? 'Next week' : 'Next day'} disabled={shiftEnergyDay(value,step)>latest} onClick={() => commit(shiftEnergyDay(value,step))}><ChevronRight size={16}/></button>
    <button className="response-button" onClick={() => commit(today)}>{weekly ? 'Current week' : 'Today'}</button>
    {weekly && <label>Recent weeks<select aria-label="Recent weeks" value={Array.from({length:12},(_,i)=>shiftEnergyDay(latest,-i*7)).includes(value)?value:''} onChange={event => event.target.value && commit(event.target.value)}><option value="" disabled>Custom week</option>{Array.from({length:12},(_,i)=>shiftEnergyDay(latest,-i*7)).map((day,i)=><option key={day} value={day}>{i===0?'Current week':i===1?'Last week':weekLabel(day)}</option>)}</select></label>}
  </div>;
}
