import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle, Plus, X, Search, Filter, CheckCircle2,
  Clock, Zap, Wrench, Wifi, HelpCircle, ChevronRight
} from 'lucide-react';
import { incidentsApi } from '../api/client';

// --- Category metadata: mirrors TICKET_CATEGORY_CODES on the backend ---
// NOTE: Tailwind's content scanner only picks up complete, literal class name
// strings — it can't resolve `bg-${accent}-900/40` at build time. Each
// category's classes are written out in full here rather than interpolated,
// so the colors actually ship in the production CSS.
const CATEGORIES = [
  { id: 'FIBER', label: 'Fiber', code: 'OF', icon: Wifi,
    activeClass: 'bg-cyan-900/40 border-cyan-500 text-cyan-400', iconClass: 'text-cyan-400' },
  { id: 'POWER', label: 'Power', code: 'PW', icon: Zap,
    activeClass: 'bg-orange-900/40 border-orange-500 text-orange-400', iconClass: 'text-orange-400' },
  { id: 'TECHNICAL', label: 'Technical', code: 'TN', icon: Wrench,
    activeClass: 'bg-purple-900/40 border-purple-500 text-purple-400', iconClass: 'text-purple-400' },
  { id: 'MAINTENANCE', label: 'Maintenance', code: 'MA', icon: Clock,
    activeClass: 'bg-blue-900/40 border-blue-500 text-blue-400', iconClass: 'text-blue-400' },
  { id: 'OTHER', label: 'Other', code: 'OT', icon: HelpCircle,
    activeClass: 'bg-gray-900/40 border-gray-500 text-gray-400', iconClass: 'text-gray-400' },
];
const categoryMeta = (id) => CATEGORIES.find(c => c.id === id) || CATEGORIES[4];

const SEVERITIES = ['Critical', 'High', 'Medium', 'Low'];
// Values match the DB CHECK constraint exactly (lowercase). Labels are
// what staff actually see — this is the only place the two need to differ.
const STATUSES = [
  { value: 'open', label: 'Open' },
  { value: 'investigating', label: 'In Progress' },
  { value: 'pending', label: 'Pending' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
  { value: 'aborted', label: 'Aborted' },
];
const CLOSED_STATUSES = ['resolved', 'closed', 'aborted'];
const statusLabel = (value) => STATUSES.find(s => s.value === value)?.label || value;

const EMPTY_INCIDENT = {
  ticket_category: 'FIBER',
  incident_type: '',
  short_description: '',
  description: '',
  severity: 'Medium',
  is_planned: false,
  network_route: '',
  network_node: '',
  responsible_person: '',
  opened_by: '',
};

const EMPTY_RESOLUTION = {
  status: 'resolved',
  resolution_team: '',
  resolution_method: '',
  rfo_root_cause: '',
  rfo_root_cause_detail: '',
  closed_by: '',
};

const IncidentManagement = () => {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [filters, setFilters] = useState({ status: '', severity: '', ticket_category: '', search: '' });
  const [searchInput, setSearchInput] = useState('');

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isResolveOpen, setIsResolveOpen] = useState(false);
  const [selectedIncident, setSelectedIncident] = useState(null);

  const [newIncident, setNewIncident] = useState(EMPTY_INCIDENT);
  const [resolution, setResolution] = useState(EMPTY_RESOLUTION);
  const [submitting, setSubmitting] = useState(false);

  const fetchIncidents = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params = {};
      if (filters.status) params.status = filters.status;
      if (filters.severity) params.severity = filters.severity;
      if (filters.ticket_category) params.ticket_category = filters.ticket_category;
      if (filters.search) params.search = filters.search;
      const response = await incidentsApi.getIncidents(params);
      setIncidents(response.data);
    } catch (err) {
      setError('Could not load incidents. Confirm the backend is running.');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchIncidents(); }, [fetchIncidents]);

  // Debounce the free-text search so we're not firing a request per keystroke
  useEffect(() => {
    const t = setTimeout(() => setFilters(f => ({ ...f, search: searchInput })), 350);
    return () => clearTimeout(t);
  }, [searchInput]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await incidentsApi.createIncident(newIncident);
      setIsCreateOpen(false);
      setNewIncident(EMPTY_INCIDENT);
      fetchIncidents();
    } catch (err) {
      alert('Could not save this incident. Check the required fields and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const openResolve = (incident) => {
    setSelectedIncident(incident);
    setResolution(EMPTY_RESOLUTION);
    setIsResolveOpen(true);
  };

  const handleResolve = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload = { ...resolution };
      if (resolution.status === 'resolved' || resolution.status === 'closed') {
        payload.resolved_at = new Date().toISOString();
      }
      await incidentsApi.updateIncident(selectedIncident.incident_id, payload);
      setIsResolveOpen(false);
      setSelectedIncident(null);
      fetchIncidents();
    } catch (err) {
      alert('Could not update this incident. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const severityBadge = (severity) => {
    const base = 'px-2.5 py-1 text-xs font-semibold rounded-full border';
    switch (severity) {
      case 'Critical': return `${base} bg-red-900/50 text-red-400 border-red-700`;
      case 'High': return `${base} bg-orange-900/50 text-orange-400 border-orange-700`;
      case 'Medium': return `${base} bg-yellow-900/50 text-yellow-400 border-yellow-700`;
      case 'Low': return `${base} bg-lime-900/50 text-lime-400 border-lime-700`;
      default: return `${base} bg-gray-800 text-gray-400 border-gray-600`;
    }
  };

  const statusBadge = (status) => {
    const base = 'px-2.5 py-1 text-xs font-semibold rounded-full border';
    switch (status) {
      case 'open': return `${base} bg-yellow-900/50 text-yellow-400 border-yellow-700`;
      case 'investigating': return `${base} bg-blue-900/50 text-blue-400 border-blue-700`;
      case 'pending': return `${base} bg-purple-900/50 text-purple-400 border-purple-700`;
      case 'resolved': return `${base} bg-lime-900/50 text-lime-400 border-lime-700`;
      case 'closed': return `${base} bg-green-900/50 text-green-400 border-green-700`;
      case 'aborted': return `${base} bg-gray-800 text-gray-400 border-gray-600`;
      default: return `${base} bg-charcoal-800 text-gray-300 border-charcoal-700`;
    }
  };

  const openCount = incidents.filter(i => !CLOSED_STATUSES.includes(i.status)).length;
  const criticalCount = incidents.filter(i => i.severity === 'Critical' && !CLOSED_STATUSES.includes(i.status)).length;

  const inputClass = "w-full bg-charcoal-800 border border-charcoal-700 rounded p-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50";
  const labelClass = "block text-xs font-medium text-gray-400 mb-1";

  return (
    <div className="p-6 h-full flex flex-col space-y-6 overflow-hidden">
      {/* Header */}
      <div className="flex justify-between items-center shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center">
            <AlertTriangle className="mr-3 text-cyan-400" /> Incident Management
          </h1>
          <p className="text-gray-400 text-sm mt-1">Log and track incidents — ticket numbers are generated automatically.</p>
        </div>
        <button
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors shadow-lg shadow-cyan-900/50"
        >
          <Plus size={16} className="mr-2" /> Log Incident
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-4 shrink-0">
        <div className="bg-charcoal-800 p-4 rounded-xl border border-charcoal-700">
          <h3 className="text-gray-400 text-xs mb-1">Total Incidents</h3>
          <p className="text-2xl font-bold text-white">{incidents.length}</p>
        </div>
        <div className="bg-charcoal-800 p-4 rounded-xl border border-charcoal-700">
          <h3 className="text-gray-400 text-xs mb-1">Open / In Progress</h3>
          <p className="text-2xl font-bold text-cyan-400">{openCount}</p>
        </div>
        <div className="bg-charcoal-800 p-4 rounded-xl border border-charcoal-700">
          <h3 className="text-gray-400 text-xs mb-1">Open Critical</h3>
          <p className="text-2xl font-bold text-red-400">{criticalCount}</p>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder="Search TT number or description..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full bg-charcoal-800 border border-charcoal-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
          />
        </div>
        <Filter size={14} className="text-gray-500" />
        <select value={filters.ticket_category} onChange={(e) => setFilters(f => ({ ...f, ticket_category: e.target.value }))} className="bg-charcoal-800 border border-charcoal-700 rounded-lg px-3 py-2 text-sm text-gray-300">
          <option value="">All Categories</option>
          {CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
        <select value={filters.severity} onChange={(e) => setFilters(f => ({ ...f, severity: e.target.value }))} className="bg-charcoal-800 border border-charcoal-700 rounded-lg px-3 py-2 text-sm text-gray-300">
          <option value="">All Severities</option>
          {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filters.status} onChange={(e) => setFilters(f => ({ ...f, status: e.target.value }))} className="bg-charcoal-800 border border-charcoal-700 rounded-lg px-3 py-2 text-sm text-gray-300">
          <option value="">All Statuses</option>
          {STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {loading ? (
          <div className="flex justify-center items-center h-full text-gray-400">Loading incidents...</div>
        ) : error ? (
          <div className="flex justify-center items-center h-full text-red-400 text-sm">{error}</div>
        ) : incidents.length === 0 ? (
          <div className="flex flex-col justify-center items-center h-full text-gray-500 text-sm">
            <AlertTriangle className="mb-2 text-gray-600" size={28} />
            No incidents match these filters.
          </div>
        ) : (
          <div className="bg-charcoal-900 border border-charcoal-800 rounded-xl overflow-hidden shadow-2xl overflow-y-auto h-full">
            <table className="w-full text-left text-sm text-gray-300">
              <thead className="text-xs text-gray-400 bg-charcoal-800/50 uppercase border-b border-charcoal-700 sticky top-0 backdrop-blur-md">
                <tr>
                  <th className="px-6 py-4">TT Number</th>
                  <th className="px-6 py-4">Description</th>
                  <th className="px-6 py-4">Severity</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4">Reported</th>
                  <th className="px-6 py-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((incident) => {
                  const meta = categoryMeta(incident.ticket_category);
                  const Icon = meta.icon;
                  const isOpen = !CLOSED_STATUSES.includes(incident.status);
                  return (
                    <tr key={incident.incident_id} className="border-b border-charcoal-800 hover:bg-charcoal-800/30 transition-colors">
                      <td className="px-6 py-4 font-mono font-medium text-cyan-400">
                        <div className="flex items-center">
                          <Icon size={14} className={`mr-2 ${meta.iconClass}`} />
                          {incident.tt_number || 'Pending'}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-white font-medium max-w-xs">
                        {incident.short_description || incident.incident_type}
                        <div className="text-xs text-gray-500 font-normal mt-0.5 truncate">{incident.network_route || incident.network_node || ''}</div>
                      </td>
                      <td className="px-6 py-4"><span className={severityBadge(incident.severity)}>{incident.severity || 'Unset'}</span></td>
                      <td className="px-6 py-4"><span className={statusBadge(incident.status)}>{statusLabel(incident.status)}</span></td>
                      <td className="px-6 py-4 text-xs text-gray-400">
                        {incident.reported_at ? new Date(incident.reported_at).toLocaleDateString() : '-'}
                      </td>
                      <td className="px-6 py-4">
                        {isOpen ? (
                          <button onClick={() => openResolve(incident)} className="text-lime-400 hover:text-lime-300 text-xs font-semibold flex items-center bg-lime-900/30 px-3 py-1.5 rounded">
                            <CheckCircle2 size={14} className="mr-1" /> Resolve
                          </button>
                        ) : (
                          <span className="text-xs text-gray-600 flex items-center"><CheckCircle2 size={14} className="mr-1" /> Closed</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* --- LOG INCIDENT MODAL --- */}
      {isCreateOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-charcoal-900 border border-charcoal-700 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden max-h-[90vh] flex flex-col">
            <div className="flex justify-between items-center p-5 border-b border-charcoal-800 bg-charcoal-800/30 shrink-0">
              <h2 className="text-lg font-bold text-white flex items-center">
                <AlertTriangle className="mr-2 text-cyan-400" /> Log Incident
              </h2>
              <button onClick={() => setIsCreateOpen(false)} className="text-gray-400 hover:text-white"><X size={20} /></button>
            </div>
            <form onSubmit={handleCreate} className="p-6 space-y-4 overflow-y-auto">
              <div>
                <label className={labelClass}>Category * <span className="text-gray-600">(sets the ticket prefix)</span></label>
                <div className="grid grid-cols-5 gap-2">
                  {CATEGORIES.map(c => {
                    const Icon = c.icon;
                    const active = newIncident.ticket_category === c.id;
                    return (
                      <button
                        type="button"
                        key={c.id}
                        onClick={() => setNewIncident({ ...newIncident, ticket_category: c.id })}
                        className={`flex flex-col items-center py-2 rounded-lg border text-xs transition-colors ${
                          active ? c.activeClass : 'bg-charcoal-800 border-charcoal-700 text-gray-400 hover:border-charcoal-600'
                        }`}
                      >
                        <Icon size={16} className="mb-1" />
                        {c.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className={labelClass}>Incident Type *</label>
                <input type="text" required placeholder="e.g. Fiber Incident, Power Issue"
                  value={newIncident.incident_type}
                  onChange={(e) => setNewIncident({ ...newIncident, incident_type: e.target.value })}
                  className={inputClass} />
              </div>

              <div>
                <label className={labelClass}>Short Description *</label>
                <input type="text" required
                  value={newIncident.short_description}
                  onChange={(e) => setNewIncident({ ...newIncident, short_description: e.target.value })}
                  className={inputClass} />
              </div>

              <div>
                <label className={labelClass}>Notes / Detail</label>
                <textarea rows={3}
                  value={newIncident.description}
                  onChange={(e) => setNewIncident({ ...newIncident, description: e.target.value })}
                  className={inputClass} />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelClass}>Severity</label>
                  <select value={newIncident.severity} onChange={(e) => setNewIncident({ ...newIncident, severity: e.target.value })} className={inputClass}>
                    {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div className="flex items-center mt-6">
                  <input type="checkbox" checked={newIncident.is_planned}
                    onChange={(e) => setNewIncident({ ...newIncident, is_planned: e.target.checked })}
                    className="w-4 h-4 rounded border-charcoal-700 text-cyan-500 bg-charcoal-800" />
                  <label className="ml-2 text-sm text-gray-300">Planned activity</label>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelClass}>Network Route</label>
                  <input type="text" value={newIncident.network_route}
                    onChange={(e) => setNewIncident({ ...newIncident, network_route: e.target.value })}
                    className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Network Node / Facility</label>
                  <input type="text" value={newIncident.network_node}
                    onChange={(e) => setNewIncident({ ...newIncident, network_node: e.target.value })}
                    className={inputClass} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelClass}>Responsible Person</label>
                  <input type="text" value={newIncident.responsible_person}
                    onChange={(e) => setNewIncident({ ...newIncident, responsible_person: e.target.value })}
                    className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Opened By *</label>
                  <input type="text" required value={newIncident.opened_by}
                    onChange={(e) => setNewIncident({ ...newIncident, opened_by: e.target.value })}
                    className={inputClass} />
                </div>
              </div>

              <div className="flex justify-end pt-4 border-t border-charcoal-800 space-x-3">
                <button type="button" onClick={() => setIsCreateOpen(false)} className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-300 hover:bg-charcoal-800 transition-colors">Cancel</button>
                <button type="submit" disabled={submitting} className="px-4 py-2 rounded-lg text-sm font-semibold bg-cyan-600 text-white hover:bg-cyan-500 transition-colors disabled:opacity-50 flex items-center">
                  {submitting ? 'Saving...' : 'Save & Generate Ticket'} <ChevronRight size={16} className="ml-1" />
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- RESOLVE / UPDATE MODAL --- */}
      {isResolveOpen && selectedIncident && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-charcoal-900 border border-charcoal-700 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden max-h-[90vh] flex flex-col">
            <div className="flex justify-between items-center p-5 border-b border-charcoal-800 bg-charcoal-800/30 shrink-0">
              <h2 className="text-lg font-bold text-white flex items-center">
                <CheckCircle2 className="mr-2 text-lime-400" /> Update {selectedIncident.tt_number}
              </h2>
              <button onClick={() => setIsResolveOpen(false)} className="text-gray-400 hover:text-white"><X size={20} /></button>
            </div>
            <form onSubmit={handleResolve} className="p-6 space-y-4 overflow-y-auto">
              <div>
                <label className={labelClass}>Status</label>
                <select value={resolution.status} onChange={(e) => setResolution({ ...resolution, status: e.target.value })} className={inputClass}>
                  {STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelClass}>Resolution Team</label>
                  <input type="text" value={resolution.resolution_team}
                    onChange={(e) => setResolution({ ...resolution, resolution_team: e.target.value })}
                    className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Resolution Method</label>
                  <input type="text" value={resolution.resolution_method}
                    onChange={(e) => setResolution({ ...resolution, resolution_method: e.target.value })}
                    className={inputClass} />
                </div>
              </div>
              <div>
                <label className={labelClass}>Root Cause</label>
                <input type="text" value={resolution.rfo_root_cause}
                  onChange={(e) => setResolution({ ...resolution, rfo_root_cause: e.target.value })}
                  className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Root Cause Detail</label>
                <textarea rows={3} value={resolution.rfo_root_cause_detail}
                  onChange={(e) => setResolution({ ...resolution, rfo_root_cause_detail: e.target.value })}
                  className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Closed By</label>
                <input type="text" value={resolution.closed_by}
                  onChange={(e) => setResolution({ ...resolution, closed_by: e.target.value })}
                  className={inputClass} />
              </div>
              <div className="flex justify-end pt-4 border-t border-charcoal-800 space-x-3">
                <button type="button" onClick={() => setIsResolveOpen(false)} className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-300 hover:bg-charcoal-800 transition-colors">Cancel</button>
                <button type="submit" disabled={submitting} className="px-4 py-2 rounded-lg text-sm font-semibold bg-lime-600 text-white hover:bg-lime-500 transition-colors disabled:opacity-50">
                  {submitting ? 'Saving...' : 'Save Update'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default IncidentManagement;
