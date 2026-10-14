import apiClient from './client';
export const operationsApi = {
  summary: () => apiClient.get('/operations/summary'),
  engineers: () => apiClient.get('/operations/engineers'),
  services: () => apiClient.get('/operations/services'),
  policies: () => apiClient.get('/operations/policies'),
  createEngineer: data => apiClient.post('/operations/engineers',data),
  enableEngineer: (id,enabled) => apiClient.patch(`/operations/engineers/${id}`,{enabled}),
  createPolicy: data => apiClient.post('/operations/policies',data),
  previewPolicies: () => apiClient.post('/operations/policies/preview'),
  details: id => apiClient.get(`/operations/incidents/${id}`),
  assign: (id,engineerId) => apiClient.post(`/operations/incidents/${id}/assign`,{engineer_id:engineerId}),
  acknowledge: id => apiClient.post(`/operations/incidents/${id}/acknowledge`),
  applyPolicy: id => apiClient.post(`/operations/incidents/${id}/policy`),
  confirmOutage: (id,data) => apiClient.post(`/operations/incidents/${id}/outages`,data),
  restore: (id,data) => apiClient.post(`/operations/outages/${id}/restore`,data),
  drafts: id => apiClient.get('/operations/drafts',{params:{incident_id:id}}),
  reviewDraft: (id,data) => apiClient.patch(`/operations/drafts/${id}`,data),
  reports: start => apiClient.get('/operations/reports',{params:{start}}),
};
export function operationError(error) {
  const detail = error.response?.data?.detail;
  return typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(value => value.msg).join('; ') : error.message || 'Request failed';
}
export function watTime(value) {
  if (!value) return 'Not recorded';
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`;
  return `${new Date(normalized).toLocaleString('en-GB',{timeZone:'Africa/Lagos',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})} WAT`;
}
export function localWatInput() { return new Date(Date.now()+3600000).toISOString().slice(0,19); }
export function fromWatInput(value) { return new Date(`${value.length===16?`${value}:00`:value}+01:00`).toISOString(); }
