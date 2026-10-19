import { healthFixture, historyFixture } from './health.js';
import { dailyEnergy, weeklyEnergy } from './energy.js';

export const DEMO_IDENTITY = Object.freeze({
  id: 'demo-synthetic-noc-admin',
  name: 'DEMO · Synthetic NOC Admin',
  email: 'synthetic.admin@demo.invalid',
  verified: false,
  roles: ['NOC.Admin'],
  demo: true,
});

export const DEMO_AUTH_CONFIG = Object.freeze({
  mode: 'demo', configured: true, tenant_id: null, client_id: null, scope: null,
});

const minutes = value => new Date(Date.now() - value * 60000).toISOString();
const ahead = value => new Date(Date.now() + value * 60000).toISOString();

function incidents(stale) {
  const shift = stale ? 45 : 0;
  return [
    { incident_id: 'demo-inc-1042', tt_number: 'TT-DEMO-1042', incident_type: 'Fibre cut', short_description: 'Synthetic: Lekki–Ajah backbone cut, 48F cable', status: 'investigating', severity: 'Critical', ticket_category: 'Infrastructure', network_node: 'LEKKP01', network_route: 'LKK-AJH-01', reported_at: minutes(38 + shift), responsible_person: null, assigned_engineer_id: 'demo-eng-1', acknowledged_at: minutes(30 + shift), ack_deadline_at: minutes(8 + shift), restore_deadline_at: ahead(202 - shift), ack_target_state: 'met', restore_target_state: 'pending', escalation_level: 1, resolved_at: null, resolution_method: null, rfo_root_cause: null },
    { incident_id: 'demo-inc-1041', tt_number: 'TT-DEMO-1041', incident_type: 'Power', short_description: 'Synthetic: Ademola site on battery, generator not starting', status: 'open', severity: 'High', ticket_category: 'Energy', network_node: 'ADEMP01', network_route: null, reported_at: minutes(74 + shift), responsible_person: 'Shift lead (legacy text)', assigned_engineer_id: null, acknowledged_at: null, ack_deadline_at: minutes(44 + shift), restore_deadline_at: ahead(166 - shift), ack_target_state: 'breached', restore_target_state: 'pending', escalation_level: 2, resolved_at: null, resolution_method: null, rfo_root_cause: null },
    { incident_id: 'demo-inc-1039', tt_number: 'TT-DEMO-1039', incident_type: 'Customer fault', short_description: 'Synthetic: FTTH customer LOS at NAP-VI-014', status: 'pending', severity: 'Medium', ticket_category: 'FTTH', network_node: 'NAP-VI-014', network_route: null, reported_at: minutes(260 + shift), responsible_person: null, assigned_engineer_id: 'demo-eng-2', acknowledged_at: minutes(250 + shift), ack_deadline_at: minutes(200 + shift), restore_deadline_at: minutes(20 + shift), ack_target_state: 'met', restore_target_state: 'breached', escalation_level: 3, resolved_at: null, resolution_method: null, rfo_root_cause: null },
    { incident_id: 'demo-inc-1031', tt_number: 'TT-DEMO-1031', incident_type: 'Latency', short_description: 'Synthetic: DIA latency spike, resolved after reroute', status: 'resolved', severity: 'Low', ticket_category: 'Service', network_node: 'PROJN01', network_route: 'PRJ-VI-02', reported_at: minutes(1500), responsible_person: null, assigned_engineer_id: 'demo-eng-1', acknowledged_at: minutes(1490), ack_deadline_at: minutes(1470), restore_deadline_at: minutes(1260), ack_target_state: 'met', restore_target_state: 'met', escalation_level: 0, resolved_at: minutes(1380), resolution_method: 'Traffic reroute', rfo_root_cause: 'Congested upstream peer (synthetic)' },
  ];
}

const engineers = [
  { engineer_id: 'demo-eng-1', name: 'Synthetic Engineer A', email: 'engineer.a@demo.invalid', team: 'NOC Engineering', enabled: true },
  { engineer_id: 'demo-eng-2', name: 'Synthetic Engineer B', email: 'engineer.b@demo.invalid', team: 'FTTH Field', enabled: true },
  { engineer_id: 'demo-eng-3', name: 'Synthetic Engineer C', email: 'engineer.c@demo.invalid', team: 'Energy', enabled: false },
];
const services = [
  { id: 'demo-svc-01', service_id: 'demo-svc-01', name: 'Demo Bank Ltd · DIA 200 Mbps', customer: 'Demo Bank Ltd', service_type: 'DIA' },
  { id: 'demo-svc-02', service_id: 'demo-svc-02', name: 'Example Retail · FTTH 50 Mbps', customer: 'Example Retail', service_type: 'FTTH' },
];

function orders() {
  const base = { service_category: 'FTTH', bandwidth: '50 Mbps', metrics: { acceptance_doc_url: null }, drop_cable_code: null, drop_tech_name: null, nap_code: null, nap_id: null, nap_port: null, service_id: null, activated_service_id: null };
  return [
    { ...base, order_id: 'demo-ord-1', work_order_id: 'WO-DEMO-301', service_order_number: 'SO-DEMO-301', fn_number: 'FN-DEMO-0301', customer_name: 'Synthetic Customer 301', isp: 'MTNN', status: 'REQUESTED', service_address: '1 Example Close, Victoria Island' },
    { ...base, order_id: 'demo-ord-2', work_order_id: 'WO-DEMO-302', service_order_number: 'SO-DEMO-302', fn_number: 'FN-DEMO-0302', customer_name: 'Synthetic Customer 302', isp: 'METROREACH', status: 'SCHEDULED', service_address: '2 Sample Street, Lekki', nap_code: 'NAP-LK-007', nap_id: 'demo-nap-7', nap_port: 3 },
    { ...base, order_id: 'demo-ord-3', work_order_id: 'WO-DEMO-303', service_order_number: 'SO-DEMO-303', fn_number: 'FN-DEMO-0303', customer_name: 'Synthetic Customer 303', isp: 'MANGONET', status: 'IN_PROGRESS', service_address: '3 Placeholder Road, Ikoyi', nap_code: 'NAP-IK-002', nap_id: 'demo-nap-2', nap_port: 5, drop_tech_name: 'Synthetic Field Tech' },
    { ...base, order_id: 'demo-ord-4', work_order_id: 'WO-DEMO-304', service_order_number: 'SO-DEMO-304', fn_number: 'FN-DEMO-0304', customer_name: 'Synthetic Customer 304', isp: 'MTNN', status: 'PENDING_ACCEPTANCE', service_address: '4 Fixture Avenue, Ajah', nap_code: 'NAP-AJ-011', nap_id: 'demo-nap-11', nap_port: 1, drop_cable_code: 'DC-DEMO-04' },
    { ...base, order_id: 'demo-ord-5', work_order_id: 'WO-DEMO-305', service_order_number: 'SO-DEMO-305', fn_number: 'FN-DEMO-0305', customer_name: 'Example Retail', isp: 'MTNN', status: 'MONITORED', service_address: '5 Example Close, Victoria Island', nap_code: 'NAP-VI-014', nap_id: 'demo-nap-14', nap_port: 2, service_id: 'demo-svc-02', activated_service_id: 'demo-svc-02' },
  ];
}

function activities(stale) {
  const shift = stale ? 45 : 0;
  return [
    { activity_id: 'demo-act-1', category: 'Handover', title: 'Synthetic: Night shift handover', description: 'Backbone cut TT-DEMO-1042 under investigation. Field team dispatched.', person: 'Synthetic Operator', shift: 'Night', status: 'open', handover: true, affected_system: 'LKK-AJH-01', ticket_category: 'Infrastructure', ticket_id: 'TT-DEMO-1042', vendor_reference: null, created_at: minutes(20 + shift), due_at: ahead(60), scheduled_at: null, incident_id: 'demo-inc-1042', order_id: null },
    { activity_id: 'demo-act-2', category: 'Maintenance', title: 'Synthetic: Planned generator service, Ademola', description: 'Vendor visit scheduled. Battery autonomy verified at 4 hours (sample).', person: 'Synthetic Engineer C', shift: 'Day', status: 'scheduled', handover: false, affected_system: 'ADEMP01', ticket_category: 'Energy', ticket_id: null, vendor_reference: 'VND-DEMO-88', created_at: minutes(180 + shift), due_at: null, scheduled_at: ahead(720), incident_id: null, order_id: null },
    { activity_id: 'demo-act-3', category: 'FTTH', title: 'Synthetic: Acceptance check for FN-DEMO-0304', description: 'Light levels recorded; awaiting NOC acceptance.', person: 'Synthetic Operator', shift: 'Day', status: 'completed', handover: false, affected_system: 'NAP-AJ-011', ticket_category: 'FTTH', ticket_id: null, vendor_reference: null, created_at: minutes(300 + shift), due_at: null, scheduled_at: null, incident_id: null, order_id: 'demo-ord-4' },
  ];
}

const topology = {
  nodes: [
    { id: 'core-1', type: 'core', position: { x: 0, y: 0 }, data: { label: 'DEMO Core POP', type: 'core', badge: 'POP' } },
    { id: 'cable-1', type: 'cable', position: { x: 0, y: 120 }, data: { label: 'Synthetic 48F · LKK-AJH-01', type: 'cable', total_cores: 48, recorded_cores: 31 } },
    { id: 'cable-2', type: 'cable', position: { x: 260, y: 120 }, data: { label: 'Synthetic 24F · PRJ-VI-02', type: 'cable', total_cores: 24, recorded_cores: 24 } },
  ],
  edges: [
    { id: 'e-core-1', source: 'core-1', target: 'cable-1', type: 'fibre', style: { stroke: '#f87171' } },
    { id: 'e-core-2', source: 'core-1', target: 'cable-2', type: 'fibre', style: {} },
  ],
};
const expansions = {
  'cable-1': { nodes: [{ id: 'split-1', type: 'primary_splitter', position: { x: 0, y: 240 }, data: { label: 'Synthetic splitter 1:8', type: 'primary_splitter' } }, { id: 'ap-1', type: 'access_point', position: { x: 0, y: 360 }, data: { label: 'NAP-AJ-011', type: 'access_point' } }], edges: [{ id: 'e-c1-s1', source: 'cable-1', target: 'split-1', type: 'fibre' }, { id: 'e-s1-ap1', source: 'split-1', target: 'ap-1', type: 'fibre' }] },
  'cable-2': { nodes: [{ id: 'dia-1', type: 'dia_end', position: { x: 260, y: 240 }, data: { label: 'Demo Bank Ltd · DIA', type: 'dia_end' } }], edges: [{ id: 'e-c2-d1', source: 'cable-2', target: 'dia-1', type: 'fibre' }] },
};
const impact = { customer_count: 2, service_count: 2, services: services.map(row => ({ service_id: row.id, customer: row.customer, service_type: row.service_type, alternate_path: null })) };

function geography(scenario) {
  if (scenario === 'empty') return { type: 'FeatureCollection', features: [], routes: [] };
  const route = (id, name, coordinates, alarms = []) => ({ type: 'Feature', geometry: { type: 'LineString', coordinates }, properties: { kind: 'route', name, inventory_route_id: id, status: alarms.length ? 'down' : 'live', length_m: 9400, recorded_km: 9.4, monitoring_alarms: alarms, location_source: 'synthetic' } });
  const site = (name, coordinates, node_type) => ({ type: 'Feature', geometry: { type: 'Point', coordinates }, properties: { kind: 'node', name, node_type, status: 'live', location_source: 'synthetic' } });
  return { type: 'FeatureCollection',
    features: [
      route('demo-route-1', 'Synthetic LKK-AJH-01', [[3.4746, 6.4474], [3.5352, 6.4389], [3.5852, 6.4683]], [{ sensor_id: 'DEMO-2201', state: 'down', observed_at: minutes(38) }]),
      route('demo-route-2', 'Synthetic PRJ-VI-02', [[3.4219, 6.4281], [3.4386, 6.4318], [3.4746, 6.4474]]),
      site('DEMO Core POP', [3.4746, 6.4474], 'pop'), site('Synthetic closure VI-3', [3.4386, 6.4318], 'closure'), site('Demo Bank Ltd', [3.4219, 6.4281], 'customer'),
    ],
    routes: [{ route_id: 'demo-route-1', name: 'Synthetic LKK-AJH-01' }, { route_id: 'demo-route-2', name: 'Synthetic PRJ-VI-02' }] };
}

function documents(scenario) {
  if (scenario === 'empty') return { items: [], total: 0 };
  const version = (n, name) => ({ version_id: `demo-ver-${n}`, revision: 1, original_filename: name, byte_size: 182000, sha: 'demo0000000000000000000000000000000000000000000000000000000000ff', change_note: 'Synthetic fixture', uploaded_by: DEMO_IDENTITY.id, created_at: minutes(2000 + n) });
  const items = [
    { document_id: 'demo-doc-1', title: 'Synthetic RCA · Backbone cut sample', document_type: 'rca', visibility: 'internal', review_state: 'approved', rag_state: 'not_indexed', incident_id: 'demo-inc-1031', order_id: null, service_id: null, owner_id: DEMO_IDENTITY.id, latest_version: version(1, 'demo-rca.pdf') },
    { document_id: 'demo-doc-2', title: 'Synthetic customer handover · FN-DEMO-0305', document_type: 'customer_handover', visibility: 'internal', review_state: 'pending_review', rag_state: 'not_indexed', incident_id: null, order_id: 'demo-ord-5', service_id: 'demo-svc-02', owner_id: DEMO_IDENTITY.id, latest_version: version(2, 'demo-handover.pdf') },
  ];
  return { items, total: items.length };
}

function mailItems(scenario) {
  const items = scenario === 'empty' ? [] : [
    { item_id: 'demo-mail-1', subject: 'Synthetic: Customer reports no internet', sender: 'customer@demo.invalid', excerpt: 'Sample excerpt. Our office link has been down since morning…', received_at: minutes(55), entered_at: minutes(50), state: 'needs_review', incident_id: null, order_id: null, reviewed_at: null, reviewed_by: null, action_note: null, classification: { category: 'customer_fault', priority: 'high', references: { fn_numbers: ['FN-DEMO-0305'] }, rule_version: 'demo-1', signals: [{ reason: 'Synthetic service-impact phrase', matched: 'no internet' }] } },
    { item_id: 'demo-mail-2', subject: 'Synthetic: Vendor maintenance notice', sender: 'vendor@demo.invalid', excerpt: 'Sample excerpt. Planned works on the upstream circuit…', received_at: minutes(400), entered_at: minutes(395), state: 'acknowledged', incident_id: null, order_id: null, reviewed_at: minutes(380), reviewed_by: DEMO_IDENTITY.id, action_note: 'Logged as planned activity (sample).', classification: { category: 'maintenance', priority: 'normal', references: {}, rule_version: 'demo-1', signals: [{ reason: 'Synthetic maintenance phrase', matched: 'planned works' }] } },
  ];
  return { items, total: items.length, counts: { needs_review: scenario === 'empty' ? 0 : 1, acknowledged: scenario === 'empty' ? 0 : 1, dismissed: 0 } };
}

function energyStatus(stale) {
  const checked = stale ? minutes(95) : minutes(2);
  return { trial_enabled: false, metadata: { defaultDate: '2026-10-17' },
    last_import: { source: 'DEMO-RawData.xlsx (synthetic)', record_count: 96, entered_at: checked },
    sync: { enabled: true, transport: 'file_delivery', configured: true, connected: !stale, agent_online: !stale, agent_last_seen_at: checked, worker_healthy: !stale, pending: false, request_state: stale ? 'delayed' : 'idle', requested_at: null, interval_seconds: 300, last_checked_at: checked, last_success_at: checked, source_modified_at: checked, next_attempt_at: ahead(3), last_error_message: stale ? 'Demo scenario: source computer has not delivered a workbook recently.' : null, active_revision_id: 'demo-rev-1' } };
}

const emptyEnergy = day => ({ date: day, start: `${day}T00:00:00+01:00`, end: `${day}T23:59:59+01:00`, sites: [], events: [], trial_coverage: {} });

const list = (scenario, rows) => (scenario === 'empty' ? [] : rows);

export function resolveFixture(method, path, query, scenario) {
  if (method === 'GET' && path === '/knowledge/sources') return { status: 200, body: { items: documents(scenario).items.map(d => ({ document_id: d.document_id, title: d.title, version: { document_id: d.document_id, version_id: d.latest_version.version_id, sha256: d.latest_version.sha256 }, revision: d.latest_version.revision, filename: d.latest_version.original_filename, supported: false, approved: false })), limit: 100 } };
  const stale = scenario === 'stale';
  if (path === '/auth/config') return { status: 200, body: DEMO_AUTH_CONFIG };
  if (path === '/auth/me') return { status: 200, body: DEMO_IDENTITY };
  if (method !== 'GET') return { status: 403, body: { detail: 'Design preview is read-only. Nothing was saved and no backend is connected.' } };
  const allIncidents = list(scenario, incidents(stale));
  const routes = [
    [/^\/incidents\/?$/, () => allIncidents.filter(row => !query.status || row.status === query.status)],
    [/^\/incidents\/([^/]+)$/, ([id]) => allIncidents.find(row => row.incident_id === id) || null],
    [/^\/activities\/?$/, () => list(scenario, activities(stale))],
    [/^\/provisioning\/?$/, () => list(scenario, orders())],
    [/^\/inventory\/assignment-options$/, () => ({ naps: list(scenario, [{ nap_id: 'demo-nap-7', nap_code: 'NAP-LK-007', available_ports: [1, 2, 4, 6] }, { nap_id: 'demo-nap-11', nap_code: 'NAP-AJ-011', available_ports: [3, 5] }]), splitters: list(scenario, [{ splitter_id: 'demo-split-1', name: 'Synthetic splitter 1:8' }]) })],
    [/^\/customers\/?$/, () => list(scenario, [{ customer_id: 'demo-cust-1', customer_name: 'Demo Bank Ltd', customer_type: 'Enterprise', email: 'noc@demo.invalid', phone: '+234 000 000 0000', address: '10 Sample Way, Victoria Island', service_id_code: 'DEMO-DIA-01' }, { customer_id: 'demo-cust-2', customer_name: 'Example Retail', customer_type: 'SME', email: 'it@demo.invalid', phone: '+234 000 000 0001', address: '5 Example Close, Victoria Island', service_id_code: 'DEMO-FTTH-02' }])],
    [/^\/services\/?$/, () => { const items = list(scenario, [{ service_id: 'demo-svc-01', customer_id: 'demo-cust-1', customer_name: 'Demo Bank Ltd', service_type: 'DIA', bandwidth_mbps: 200, status: 'active', ftth_orders: [] }, { service_id: 'demo-svc-02', customer_id: 'demo-cust-2', customer_name: 'Example Retail', service_type: 'FTTH', bandwidth_mbps: 50, status: 'active', ftth_orders: ['demo-ord-5'] }]); return { items, total: items.length }; }],
    [/^\/services\/free-cores$/, () => list(scenario, [{ core_id: 'demo-core-12', number: 12, cable: 'Synthetic 48F', route: 'LKK-AJH-01', usage_type: 'free', customer_id: null, customer_name: null, service_id_code: null }])],
    [/^\/audit\/?$/, () => ({ items: list(scenario, [{ audit_id: 'demo-audit-1', occurred_at: minutes(30), actor_id: 'demo-synthetic-noc-admin', actor_verified: false, action: 'incident.acknowledge', entity_type: 'incident', entity_id: 'demo-inc-1042', request_id: 'demo-req-1', before_state: { acknowledged_at: null }, after_state: { acknowledged_at: minutes(30) } }]), next_before: null })],
    [/^\/operations\/summary$/, () => ({ as_of: stale ? minutes(45) : minutes(0), worker: { healthy: !stale, last_seen_at: stale ? minutes(45) : minutes(0) }, unassigned: allIncidents.filter(row => !row.assigned_engineer_id && row.status !== 'resolved').length, ack_overdue: allIncidents.filter(row => row.ack_target_state === 'breached').length, restore_overdue: allIncidents.filter(row => row.restore_target_state === 'breached' && row.status !== 'resolved').length, pending_drafts: scenario === 'empty' ? 0 : 1, incidents: allIncidents.filter(row => row.status !== 'resolved') })],
    [/^\/operations\/engineers$/, () => list(scenario, engineers)],
    [/^\/operations\/services$/, () => list(scenario, services)],
    [/^\/operations\/policies$/, () => list(scenario, [{ policy_id: 'demo-pol-1', name: 'Synthetic critical target', version: 2, severity: 'Critical', service_id: null, acknowledgment_minutes: 15, restoration_minutes: 240, followup_minutes: 60, default_engineer_id: 'demo-eng-1', escalation_recipients: ['duty.manager@demo.invalid'], preview_only: true }])],
    [/^\/operations\/drafts$/, () => list(scenario, [{ draft_id: 'demo-draft-1', incident_id: 'demo-inc-1042', status: 'pending', audience: 'customer', created_at: minutes(25), recipients: ['noc@demo.invalid'], subject: 'Synthetic: Service disruption notice', body: 'Sample draft. We are investigating a fibre fault affecting your service. No message is sent from the design preview.' }]).filter(row => !query.incident_id || row.incident_id === query.incident_id)],
    [/^\/operations\/reports$/, () => ({ mttr_minutes: scenario === 'empty' ? null : 118.4, restored_outage_count: scenario === 'empty' ? 0 : 3, open_outage_count: scenario === 'empty' ? 0 : 1, excluded_count: 0, outage_count: scenario === 'empty' ? 0 : 4, services: list(scenario, [{ service_id: 'demo-svc-01', customer: 'Demo Bank Ltd', recorded_downtime_minutes: 212.5, outage_count: 2 }]), outages: [] })],
    [/^\/operations\/incidents\/([^/]+)$/, ([id]) => { const incident = allIncidents.find(row => row.incident_id === id); return incident ? { incident, policy: { name: 'Synthetic critical target', version: 2, preview_only: true }, candidate_services: ['demo-svc-01'], outages: [], timeline: [{ id: 'demo-tl-1', occurred_at: incident.reported_at, kind: 'reported', note: 'Synthetic incident created.' }] } : null; }],
    [/^\/monitoring\/mappings$/, () => list(scenario, [{ sensor_id: 'DEMO-2201', route_id: 'demo-route-1', last_state: 'down', last_observed_at: minutes(stale ? 80 : 1), incident_id: 'demo-inc-1042' }, { sensor_id: 'DEMO-2202', cable_id: 'cable-2', last_state: 'up', last_observed_at: minutes(stale ? 80 : 1), incident_id: null }])],
    [/^\/monitoring\/events$/, () => list(scenario, [{ event_id: 'demo-evt-1', sensor_id: 'DEMO-2201', state: 'down', disposition: 'incident_linked', observed_at: minutes(38), incident_id: 'demo-inc-1042' }])],
    [/^\/monitoring\/targets$/, () => ({ cables: [{ id: 'cable-2', name: 'Synthetic 24F · PRJ-VI-02' }], routes: [{ id: 'demo-route-1', name: 'Synthetic LKK-AJH-01' }], services: services.map(row => ({ id: row.id, name: row.name })) })],
    [/^\/topology\/$/, () => (scenario === 'empty' ? { nodes: [], edges: [] } : topology)],
    [/^\/topology\/expand\/([^/]+)$/, ([id]) => expansions[id] || { nodes: [], edges: [] }],
    [/^\/topology\/(?:cable-)?impact\/([^/]+)$/, () => impact],
    [/^\/topology\/geography$/, () => geography(scenario)],
    [/^\/topology\/maps$/, () => []],
    [/^\/documents$/, () => documents(scenario)],
    [/^\/documents\/([^/]+)$/, ([id]) => { const record = documents('live').items.find(row => row.document_id === id); return record ? { ...record, versions: [record.latest_version] } : null; }],
    [/^\/knowledge\/status$/, () => ({ indexed_sources: 0, approved_sources: 0, rag_connected: false, query_available: false, approval_available: false })],
    [/^\/mail\/connection$/, () => ({ connected: false, mode: 'unavailable', mailbox: null, last_sync_at: null, rag_connected: false, retention_automation: false, requirements: ['Design preview: no mailbox is connected'] })],
    [/^\/mail\/items$/, () => mailItems(scenario)],
    [/^\/ftth\/reports$/, () => (scenario === 'empty'
      ? { start: minutes(43200), end: minutes(0), lifetime: { requests: 0, completed: 0, accepted: 0 }, period: { requests: 0, completed: 0, accepted: 0, new_incidents: 0, resolved_incidents: 0 }, active_incidents: 0, partial_histories: 0, unknown_acceptance_dates: 0, stage_durations: [], open_stage_ages: [], incident_mttr: [] }
      : { start: minutes(43200), end: minutes(0), lifetime: { requests: 5, completed: 2, accepted: 1 }, period: { requests: 5, completed: 2, accepted: 1, new_incidents: 1, resolved_incidents: 0 }, active_incidents: 1, partial_histories: 1, unknown_acceptance_dates: 0, stage_durations: [{ stage: 'SCHEDULED', samples: 4, mean_minutes: 1320.5, median_minutes: 1180 }, { stage: 'IN_PROGRESS', samples: 3, mean_minutes: 245.2, median_minutes: 210 }], open_stage_ages: [{ order_id: 'demo-ord-3', minutes: 182 }, { order_id: 'demo-ord-4', minutes: 640 }], incident_mttr: [{ category: 'Customer fault', samples: 2, mean_minutes: 96.5, median_minutes: 90 }] })],
    [/^\/ftth\/orders\/([^/]+)$/, ([id]) => { const order = orders().find(row => row.order_id === id); return order ? { order, history_complete: order.status !== 'IN_PROGRESS', events: [{ event_id: `${id}-e1`, order_id: id, from_stage: null, to_stage: 'REQUESTED', occurred_at: minutes(4000), actor_id: 'demo-synthetic-noc-admin', note: 'Synthetic request recorded.' }], incidents: [] } : null; }],
    [/^\/platform-health\/hosts$/, () => healthFixture(scenario === 'empty' ? 'Empty host list' : stale ? 'Status stale' : 'Up to date')],
    [/^\/platform-health\/hosts\/([^/]+)\/history$/, () => historyFixture(Number(query.hours) || 24, stale ? 'Status stale' : 'Up to date')],
    [/^\/energy\/status$/, () => energyStatus(stale)],
    [/^\/energy\/report$/, () => (scenario === 'empty' ? emptyEnergy(query.day || '2026-10-17') : dailyEnergy(query.day, query.source))],
    [/^\/energy\/weekly$/, () => (scenario === 'empty' ? { ...emptyEnergy(query.week_start || '2026-10-05'), days: [] } : weeklyEnergy(query.week_start, query.source))],
  ];
  for (const [pattern, build] of routes) {
    const match = path.match(pattern);
    if (match) {
      const body = build(match.slice(1));
      return body === null ? { status: 404, body: { detail: 'Not found in design preview fixtures.' } } : { status: 200, body };
    }
  }
  return { status: 404, body: { detail: `No design preview fixture for ${path}.` } };
}
