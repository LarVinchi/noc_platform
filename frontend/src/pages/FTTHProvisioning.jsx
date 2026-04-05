import React, { useState } from 'react';
import { 
  List, Layout, AlertTriangle, FileText, Plus, Activity 
} from 'lucide-react';

// Mock Data for UI Testing (Will be replaced by FastAPI backend)
const MOCK_ORDERS = [
  {
    id: 'SHANC01-FTTH-50M-00001',
    customer_name: 'Shantel Vincent',
    isp: 'MTNN',
    fn_number: 'FN509179',
    bandwidth: '50M',
    status: 'ROSETTE_TESTING',
    nap_id: 'NAP 08-090303-11',
    pfs_power: '-18.5dBm',
    nap_power: '-21.0dBm',
    rosette_power: null, // Pending
    planned_date: '2026-01-18'
  },
  {
    id: 'PENDING-ID-ALLOCATION',
    customer_name: 'Aliko Dangote',
    isp: 'MTNN',
    fn_number: null, // MISSING DATA FLAG WILL TRIGGER
    bandwidth: '100M',
    status: 'REQUESTED',
    nap_id: null, // MISSING DATA
    pfs_power: null,
    nap_power: null,
    rosette_power: null,
    planned_date: '2026-01-20'
  },
  {
    id: 'METRO-FTTH-20M-00042',
    customer_name: 'TechHub Lagos',
    isp: 'METROREACH',
    fn_number: 'N/A', // Metroreach doesn't need FN
    bandwidth: '20M',
    status: 'ACTIVE',
    nap_id: 'NAP 02-010101-05',
    pfs_power: '-16.2dBm',
    nap_power: '-19.8dBm',
    rosette_power: '-22.1dBm',
    planned_date: '2026-01-15'
  }
];

const WORKFLOW_STAGES = [
  'REQUESTED', 'PFS_TESTING', 'NAP_TESTING', 'ROSETTE_TESTING', 'DROP_INSTALLATION', 'ACTIVE'
];

const FTTHProvisioning = () => {
  const [viewType, setViewType] = useState('list'); // 'list' | 'board'
  const [orders, setOrders] = useState(MOCK_ORDERS);

  // --- Logic Helpers ---
  const getMissingData = (order) => {
    const missing = [];
    if (order.isp === 'MTNN' && !order.fn_number) missing.push('MTNN FN#');
    if (!order.nap_id) missing.push('NAP Assignment');
    return missing;
  };

  const getStatusColor = (status) => {
    if (status === 'ACTIVE') return 'text-green-400 bg-green-500/10 border-green-500/50';
    if (status === 'REQUESTED') return 'text-gray-400 bg-charcoal-800 border-charcoal-600';
    return 'text-cyan-400 bg-cyan-500/10 border-cyan-500/50'; // In progress
  };

  // --- Components ---
  const MissingDataBadge = ({ missing }) => {
    if (missing.length === 0) return null;
    return (
      <div className="flex items-center space-x-1 text-xs font-semibold text-orange-400 bg-orange-500/10 border border-orange-500/30 px-2 py-1 rounded animate-pulse w-max">
        <AlertTriangle size={12} />
        <span>Missing: {missing.join(', ')}</span>
      </div>
    );
  };

  const TableView = () => (
    <div className="overflow-x-auto bg-charcoal-900 border border-charcoal-700 rounded-lg shadow-xl">
      <table className="w-full text-left text-sm text-gray-300">
        <thead className="bg-charcoal-950 text-gray-400 uppercase text-xs tracking-wider border-b border-charcoal-700">
          <tr>
            <th className="px-4 py-3">Service ID</th>
            <th className="px-4 py-3">Customer Info</th>
            <th className="px-4 py-3">Workflow Status</th>
            <th className="px-4 py-3">Testing Telemetry</th>
            <th className="px-4 py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-charcoal-800">
          {orders.map((order, idx) => {
            const missing = getMissingData(order);
            return (
              <tr key={idx} className="hover:bg-charcoal-800/50 transition-colors">
                <td className="px-4 py-4 font-mono text-cyan-400">{order.id}</td>
                <td className="px-4 py-4">
                  <div className="font-bold text-white">{order.customer_name}</div>
                  <div className="text-xs text-gray-500">{order.isp} | {order.bandwidth}</div>
                  <MissingDataBadge missing={missing} />
                </td>
                <td className="px-4 py-4">
                  <span className={`px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${getStatusColor(order.status)}`}>
                    {order.status.replace('_', ' ')}
                  </span>
                </td>
                <td className="px-4 py-4 text-xs font-mono text-gray-400 space-y-1">
                  <div>PFS: <span className={order.pfs_power ? 'text-green-400' : 'text-gray-600'}>{order.pfs_power || 'PENDING'}</span></div>
                  <div>NAP: <span className={order.nap_power ? 'text-green-400' : 'text-gray-600'}>{order.nap_power || 'PENDING'}</span></div>
                  <div>ROS: <span className={order.rosette_power ? 'text-green-400' : 'text-gray-600'}>{order.rosette_power || 'PENDING'}</span></div>
                </td>
                <td className="px-4 py-4 text-right space-x-2">
                  <button className="p-2 text-gray-400 hover:text-cyan-400 hover:bg-charcoal-700 rounded transition-colors" title="Edit Request">
                    <AlertTriangle size={18} />
                  </button>
                  {order.status === 'ACTIVE' && (
                    <button className="p-2 text-green-400 hover:text-white hover:bg-green-600 rounded transition-colors" title="Download Acceptance Doc">
                      <FileText size={18} />
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  const BoardView = () => (
    <div className="flex space-x-4 overflow-x-auto pb-4">
      {WORKFLOW_STAGES.map(stage => (
        <div key={stage} className="min-w-[300px] bg-charcoal-900 border border-charcoal-700 rounded-lg flex flex-col max-h-[70vh]">
          <div className="p-3 border-b border-charcoal-700 bg-charcoal-950 rounded-t-lg flex justify-between items-center">
            <h3 className="font-bold text-gray-300 text-sm tracking-widest uppercase">{stage.replace('_', ' ')}</h3>
            <span className="bg-charcoal-800 text-gray-400 px-2 py-0.5 rounded text-xs font-mono">
              {orders.filter(o => o.status === stage).length}
            </span>
          </div>
          <div className="p-3 overflow-y-auto space-y-3 flex-1">
            {orders.filter(o => o.status === stage).map(order => (
              <div key={order.id} className="bg-charcoal-800 border border-charcoal-600 p-3 rounded shadow-md hover:border-cyan-500 transition-colors cursor-pointer group">
                <div className="flex justify-between items-start mb-2">
                  <span className="font-bold text-white text-sm">{order.customer_name}</span>
                  <span className="text-[10px] bg-charcoal-950 px-1.5 py-0.5 rounded text-gray-400">{order.isp}</span>
                </div>
                <div className="text-xs font-mono text-cyan-400 mb-2 truncate">{order.id}</div>
                <MissingDataBadge missing={getMissingData(order)} />
                <div className="mt-3 pt-3 border-t border-charcoal-700 flex justify-between items-center">
                  <span className="text-xs text-gray-500">{order.planned_date}</span>
                  <Activity size={14} className="text-gray-500 group-hover:text-cyan-400 transition-colors" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );

  return (
    <div className="p-6 h-full flex flex-col bg-charcoal-950 text-gray-200">
      
      {/* Header & Controls */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-wide">FTTH Provisioning Pipeline</h1>
          <p className="text-sm text-gray-400 mt-1">Track service deliveries, run telemetry tests, and generate Acceptance Docs.</p>
        </div>
        
        <div className="flex items-center space-x-4">
          {/* View Toggle */}
          <div className="flex bg-charcoal-900 p-1 rounded-lg border border-charcoal-700">
            <button 
              onClick={() => setViewType('list')}
              className={`p-2 rounded flex items-center transition-colors ${viewType === 'list' ? 'bg-charcoal-700 text-cyan-400 shadow' : 'text-gray-500 hover:text-white'}`}
            >
              <List size={16} className="mr-2" /> Table
            </button>
            <button 
              onClick={() => setViewType('board')}
              className={`p-2 rounded flex items-center transition-colors ${viewType === 'board' ? 'bg-charcoal-700 text-cyan-400 shadow' : 'text-gray-500 hover:text-white'}`}
            >
              <Layout size={16} className="mr-2" /> Board
            </button>
          </div>
          
          {/* Action Button */}
          <button className="flex items-center bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors shadow-lg shadow-cyan-900/50">
            <Plus size={16} className="mr-2" /> New FTTH Request
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden">
        {viewType === 'list' ? <TableView /> : <BoardView />}
      </div>

    </div>
  );
};

export default FTTHProvisioning;