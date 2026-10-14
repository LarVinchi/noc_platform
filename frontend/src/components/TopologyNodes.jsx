import { createElement } from 'react';
import { Handle, Position } from 'reactflow';
import { Network, Cable, Server, Router, Building2, Waypoints, Unplug, Split, CircuitBoard } from 'lucide-react';

const types = {
  core: { icon: Network, color: '#59c7ff', label: 'NETWORK ROUTE' },
  cable: { icon: Cable, color: '#7d9cff', label: 'FIBRE CABLE' },
  primary_splitter: { icon: Server, color: '#bba1ff', label: 'PFP · PRIMARY CABINET' },
  secondary_splitter: { icon: Split, color: '#be8ef5', label: 'PFS · DISTRIBUTION' },
  access_point: { icon: CircuitBoard, color: '#55d5ce', label: 'NAP · ACCESS TERMINAL' },
  cpe_outlet: { icon: Router, color: '#efbd77', label: 'ONT · CUSTOMER PREMISES' },
  dia_endpoint: { icon: Building2, color: '#efbd77', label: 'DIA · ENTERPRISE' },
  layer2_endpoint: { icon: Waypoints, color: '#efbd77', label: 'LAYER 2 · SERVICE UNI' },
  dark_fiber_endpoint: { icon: Unplug, color: '#efbd77', label: 'DARK FIBRE · PATCH PANEL' },
};

export function NetworkNode({ data, type, selected }) {
  const spec = types[type] || types.core;
  return <div className={`network-node ${selected ? 'node-selected' : ''} ${type === 'cable' ? 'network-node-cable' : ''}`} style={{ '--node-color': spec.color }}>
    <Handle type="target" position={data.direction === 'TB' ? Position.Top : Position.Left} isConnectable={false} />
    <div className="network-node-heading"><span>{spec.label}</span><i title="Inventory record; service health unverified" /></div>
    <div className="network-node-body"><div className="network-node-symbol">{createElement(spec.icon, { size: 29, strokeWidth: 1.5 })}</div><div><strong title={data.label}>{data.label}</strong><small>{data.badge || 'Inventory record'}</small></div></div>
    {type === 'cable' ? <div className="network-core-strip"><span>{data.total_cores ?? '—'} cores</span><div>{Array.from({ length: Math.min(data.total_cores || 12, 24) }, (_, index) => <i key={index} />)}</div><small>{data.recorded_cores ?? '—'} recorded</small></div> : <div className="network-node-footer"><span>{data.inventory_status ? `Inventory: ${data.inventory_status}` : 'Linked infrastructure'}</span><span>{data.total_ports ? `${data.total_ports} ports` : data.service_type || 'PASSIVE'}</span></div>}
    <Handle type="source" position={data.direction === 'TB' ? Position.Bottom : Position.Right} isConnectable={false} />
  </div>;
}
