import React, { useState, useEffect } from 'react';
import { 
  List, Layout, AlertTriangle, Plus, Activity, 
  UploadCloud, CheckCircle, X, Download, UserPlus, ShieldCheck, GripVertical
} from 'lucide-react';
import { provisioningApi } from '../api/client';

const FTTHProvisioning = () => {
  const [viewType, setViewType] = useState('list');
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  // Modals State
  const [isInstallModalOpen, setIsInstallModalOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState(null);
  
  // Form States
  const [flexscanDbm, setFlexscanDbm] = useState('');
  const [checklistCompleted, setChecklistCompleted] = useState(false);
  const [files, setFiles] = useState({ photo_nap: null, photo_routing: null, photo_rosette: null, photo_flexscan: null });
  const [newOrder, setNewOrder] = useState({ customer_name: '', service_address: '', isp: 'METROREACH', bandwidth: '100Mbps', fn_number: '', phone_number: '', email: '' });

  const fetchOrders = async () => {
    try {
      setLoading(true);
      const response = await provisioningApi.getOrders();
      setOrders(response.data);
    } catch (error) {
      console.error("Failed to fetch orders:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchOrders(); }, []);

  // --- API Handlers ---
  const handleCreateOrder = async (e) => {
    e.preventDefault();
    try {
      await provisioningApi.createOrder({ service_category: "FTTH", ...newOrder });
      setIsCreateModalOpen(false);
      setNewOrder({ customer_name: '', service_address: '', isp: 'METROREACH', bandwidth: '100Mbps', fn_number: '', phone_number: '', email: ''});
      fetchOrders();
    } catch (error) { alert("Error creating order."); }
  };

  const handleCompleteInstall = async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('flexscan_result_dbm', flexscanDbm);
    formData.append('checklist_completed', checklistCompleted);
    if (files.photo_nap) formData.append('photo_nap', files.photo_nap);
    if (files.photo_routing) formData.append('photo_routing', files.photo_routing);
    if (files.photo_rosette) formData.append('photo_rosette', files.photo_rosette);
    if (files.photo_flexscan) formData.append('photo_flexscan', files.photo_flexscan);

    try {
      await provisioningApi.completeInstallation(selectedOrder.order_id, formData);
      setIsInstallModalOpen(false);
      setFlexscanDbm(''); setChecklistCompleted(false); setFiles({ photo_nap: null, photo_routing: null, photo_rosette: null, photo_flexscan: null });
      fetchOrders();
    } catch (error) { alert("Error submitting installation. Please ensure all required fields are filled."); }
  };

  const handleAcceptOrder = async (orderId) => {
    try {
      await provisioningApi.acceptInstallation(orderId);
      fetchOrders();
    } catch (error) { alert("Failed to accept order."); }
  };

  // --- DRAG AND DROP LOGIC ---
  const handleDragStart = (e, orderId) => {
    e.dataTransfer.setData('orderId', orderId);
  };

  const handleDrop = async (e, targetStage) => {
    e.preventDefault();
    const orderId = e.dataTransfer.getData('orderId');
    const order = orders.find(o => o.order_id === orderId);

    if (!order || order.status === targetStage) return;

    // Smart UI Routing based on Business Logic
    if (targetStage === 'PENDING_ACCEPTANCE') {
      setSelectedOrder(order);
      setIsInstallModalOpen(true);
    } else if (targetStage === 'MONITORED') {
      handleAcceptOrder(order.order_id);
    } else if (targetStage === 'SCHEDULED' && order.status === 'REQUESTED') {
      alert("Please assign a NAP to this order to transition it to Scheduled.");
    } else {
      // Generic move (e.g., SCHEDULED to IN_PROGRESS)
      try {
        await provisioningApi.updateStatus(order.order_id, targetStage);
        fetchOrders();
      } catch (error) {
        alert("Failed to update status via drag and drop.");
      }
    }
  };

  const getStatusBadge = (status) => {
    const baseClasses = "px-2.5 py-1 text-xs font-semibold rounded-full border";
    switch (status) {
      case 'REQUESTED': return `${baseClasses} bg-yellow-900/50 text-yellow-400 border-yellow-700`;
      case 'SCHEDULED': return `${baseClasses} bg-blue-900/50 text-blue-400 border-blue-700`;
      case 'IN_PROGRESS': return `${baseClasses} bg-orange-900/50 text-orange-400 border-orange-700`;
      case 'PENDING_ACCEPTANCE': return `${baseClasses} bg-purple-900/50 text-purple-400 border-purple-700`;
      case 'MONITORED': return `${baseClasses} bg-green-900/50 text-green-400 border-green-700`;
      default: return `${baseClasses} bg-gray-800 text-gray-400 border-gray-600`; 
    }
  };

  const KANBAN_STAGES = [
    { id: 'REQUESTED', title: 'New Requests', color: 'border-yellow-500' },
    { id: 'SCHEDULED', title: 'Scheduled (Designed)', color: 'border-blue-500' },
    { id: 'IN_PROGRESS', title: 'In Progress', color: 'border-orange-500' },
    { id: 'PENDING_ACCEPTANCE', title: 'Pending NOC Review', color: 'border-purple-500' },
    { id: 'MONITORED', title: 'Active & Monitored', color: 'border-green-500' }
  ];

  return (
    <div className="p-6 h-full flex flex-col space-y-6 overflow-hidden">
      {/* Header Area */}
      <div className="flex justify-between items-center shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center">
            <Activity className="mr-3 text-cyan-400" /> FTTH Provisioning Pipeline
          </h1>
          <p className="text-gray-400 text-sm mt-1">Manage drop installations, test results, and Acceptance Docs.</p>
        </div>
        
        <div className="flex items-center space-x-4">
          <div className="flex bg-charcoal-900 p-1 rounded-lg border border-charcoal-700">
            <button onClick={() => setViewType('list')} className={`p-2 rounded flex items-center transition-colors ${viewType === 'list' ? 'bg-charcoal-700 text-cyan-400 shadow' : 'text-gray-500 hover:text-white'}`}>
              <List size={16} className="mr-2" /> Table
            </button>
            <button onClick={() => setViewType('board')} className={`p-2 rounded flex items-center transition-colors ${viewType === 'board' ? 'bg-charcoal-700 text-cyan-400 shadow' : 'text-gray-500 hover:text-white'}`}>
              <Layout size={16} className="mr-2" /> Board
            </button>
          </div>
          <button onClick={() => setIsCreateModalOpen(true)} className="flex items-center bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors shadow-lg shadow-cyan-900/50">
            <Plus size={16} className="mr-2" /> New FTTH Request
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {loading ? (
           <div className="flex justify-center items-center h-full text-gray-400">Loading orders...</div>
        ) : viewType === 'list' ? (
          <div className="bg-charcoal-900 border border-charcoal-800 rounded-xl overflow-hidden shadow-2xl overflow-y-auto h-full">
            <table className="w-full text-left text-sm text-gray-300">
              <thead className="text-xs text-gray-400 bg-charcoal-800/50 uppercase border-b border-charcoal-700 sticky top-0 backdrop-blur-md">
                <tr>
                  <th className="px-6 py-4">Service ID</th>
                  <th className="px-6 py-4">Customer</th>
                  <th className="px-6 py-4">ISP</th>
                  <th className="px-6 py-4">Technical Routing</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.order_id} className="border-b border-charcoal-800 hover:bg-charcoal-800/30 transition-colors">
                    <td className="px-6 py-4 font-mono font-medium text-cyan-400">{order.service_id || 'Pending Gen'}</td>
                    <td className="px-6 py-4 text-white font-medium">{order.customer_name}<div className="text-xs text-gray-500 font-normal mt-0.5">{order.bandwidth}</div></td>
                    <td className="px-6 py-4">{order.isp}</td>
                    <td className="px-6 py-4 font-mono text-xs">{order.nap_id ? `NAP Assigned` : <span className="text-red-400 flex items-center"><AlertTriangle size={12} className="mr-1"/> Needs Design</span>}</td>
                    <td className="px-6 py-4"><span className={getStatusBadge(order.status)}>{order.status.replace(/_/g, ' ')}</span></td>
                    <td className="px-6 py-4 space-x-3 flex items-center">
                      {(order.status === 'SCHEDULED' || order.status === 'IN_PROGRESS') && (
                        <button onClick={() => { setSelectedOrder(order); setIsInstallModalOpen(true); }} className="text-cyan-400 hover:text-cyan-300 text-xs font-semibold flex items-center bg-cyan-900/30 px-3 py-1.5 rounded">
                          <UploadCloud size={14} className="mr-1" /> Finish Install
                        </button>
                      )}
                      {(order.status === 'PENDING_ACCEPTANCE' || order.status === 'MONITORED') && order.metrics?.acceptance_doc_url && (
                        <a href={`http://localhost:8000${order.metrics.acceptance_doc_url}`} target="_blank" rel="noreferrer" className="text-purple-400 hover:text-purple-300 text-xs font-semibold flex items-center bg-purple-900/30 px-3 py-1.5 rounded">
                          <Download size={14} className="mr-1" /> View PDF
                        </a>
                      )}
                      {order.status === 'PENDING_ACCEPTANCE' && (
                        <button onClick={() => handleAcceptOrder(order.order_id)} className="text-lime-400 hover:text-lime-300 text-xs font-semibold flex items-center bg-lime-900/30 px-3 py-1.5 rounded">
                          <ShieldCheck size={14} className="mr-1" /> Approve
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          /* --- SMART DRAG AND DROP KANBAN BOARD --- */
          <div className="flex space-x-4 overflow-x-auto h-full pb-4">
            {KANBAN_STAGES.map(stage => (
              <div 
                key={stage.id} 
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => handleDrop(e, stage.id)}
                className="min-w-[320px] flex-1 bg-charcoal-900/50 border border-charcoal-800 rounded-xl flex flex-col h-full transition-colors hover:bg-charcoal-800/30"
              >
                <div className={`p-4 border-b-2 ${stage.color} bg-charcoal-800/30 rounded-t-xl shrink-0`}>
                  <h3 className="font-bold text-white text-sm">{stage.title}</h3>
                  <span className="text-xs text-gray-500">{orders.filter(o => o.status === stage.id).length} Orders</span>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-3">
                  {orders.filter(o => o.status === stage.id).map(order => (
                    <div 
                      key={order.order_id} 
                      draggable
                      onDragStart={(e) => handleDragStart(e, order.order_id)}
                      className="bg-charcoal-800 p-4 rounded-lg border border-charcoal-700 shadow-md cursor-grab active:cursor-grabbing hover:border-cyan-500/50 transition-colors group"
                    >
                      <div className="flex justify-between items-start mb-2">
                        <span className="font-mono text-xs text-cyan-400 flex items-center">
                          <GripVertical size={12} className="mr-1 text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                          {order.service_id}
                        </span>
                        <span className="text-[10px] uppercase font-bold text-gray-500 bg-charcoal-900 px-2 py-0.5 rounded">{order.isp}</span>
                      </div>
                      <h4 className="text-white font-semibold text-sm">{order.customer_name}</h4>
                      <p className="text-gray-400 text-xs mt-1 truncate">{order.service_address}</p>
                      
                      <div className="mt-4 flex flex-wrap gap-2">
                        {(order.status === 'SCHEDULED' || order.status === 'IN_PROGRESS') && (
                          <button onClick={() => { setSelectedOrder(order); setIsInstallModalOpen(true); }} className="text-cyan-400 hover:text-cyan-300 text-[11px] font-semibold flex items-center bg-cyan-900/30 px-2 py-1 rounded w-full justify-center">
                            <UploadCloud size={12} className="mr-1" /> Finish Install
                          </button>
                        )}
                        {(order.status === 'PENDING_ACCEPTANCE' || order.status === 'MONITORED') && order.metrics?.acceptance_doc_url && (
                          <a href={`http://localhost:8000${order.metrics.acceptance_doc_url}`} target="_blank" rel="noreferrer" className="text-purple-400 hover:text-purple-300 text-[11px] font-semibold flex items-center bg-purple-900/30 px-2 py-1 rounded flex-1 justify-center">
                            <Download size={12} className="mr-1" /> PDF
                          </a>
                        )}
                        {order.status === 'PENDING_ACCEPTANCE' && (
                          <button onClick={() => handleAcceptOrder(order.order_id)} className="text-lime-400 hover:text-lime-300 text-[11px] font-semibold flex items-center bg-lime-900/30 px-2 py-1 rounded flex-1 justify-center">
                            <ShieldCheck size={12} className="mr-1" /> Approve
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* --- NEW REQUEST MODAL --- */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-charcoal-900 border border-charcoal-700 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden">
            <div className="flex justify-between items-center p-5 border-b border-charcoal-800 bg-charcoal-800/30">
              <h2 className="text-lg font-bold text-white flex items-center">
                <UserPlus className="mr-2 text-cyan-400" /> New FTTH Request
              </h2>
              <button onClick={() => setIsCreateModalOpen(false)} className="text-gray-400 hover:text-white"><X size={20} /></button>
            </div>
            <form onSubmit={handleCreateOrder} className="p-6 space-y-4">
              <div><label className="block text-xs font-medium text-gray-400 mb-1">Customer Name *</label><input type="text" required value={newOrder.customer_name} onChange={(e) => setNewOrder({...newOrder, customer_name: e.target.value})} className="w-full bg-charcoal-800 border border-charcoal-700 rounded p-2 text-white text-sm" /></div>
              <div><label className="block text-xs font-medium text-gray-400 mb-1">Service Address *</label><input type="text" required value={newOrder.service_address} onChange={(e) => setNewOrder({...newOrder, service_address: e.target.value})} className="w-full bg-charcoal-800 border border-charcoal-700 rounded p-2 text-white text-sm" /></div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-xs font-medium text-gray-400 mb-1">ISP</label><select value={newOrder.isp} onChange={(e) => setNewOrder({...newOrder, isp: e.target.value})} className="w-full bg-charcoal-800 border border-charcoal-700 rounded p-2 text-white text-sm"><option value="METROREACH">Metroreach</option><option value="MTNN">MTNN</option><option value="MANGONET">Mangonet</option></select></div>
                <div><label className="block text-xs font-medium text-gray-400 mb-1">Bandwidth</label><input type="text" placeholder="e.g. 50Mbps" required value={newOrder.bandwidth} onChange={(e) => setNewOrder({...newOrder, bandwidth: e.target.value})} className="w-full bg-charcoal-800 border border-charcoal-700 rounded p-2 text-white text-sm" /></div>
              </div>
              {newOrder.isp === 'MTNN' && (<div><label className="block text-xs font-medium text-gray-400 mb-1">FN Number (MTNN Specific)</label><input type="text" placeholder="e.g. FN509179" value={newOrder.fn_number} onChange={(e) => setNewOrder({...newOrder, fn_number: e.target.value})} className="w-full bg-charcoal-800 border border-charcoal-700 rounded p-2 text-white text-sm" /></div>)}
              <div className="flex justify-end pt-4 border-t border-charcoal-800 space-x-3 mt-6">
                <button type="button" onClick={() => setIsCreateModalOpen(false)} className="px-4 py-2 rounded text-sm font-semibold text-gray-300 hover:bg-charcoal-800">Cancel</button>
                <button type="submit" className="px-4 py-2 rounded text-sm font-semibold bg-cyan-600 text-white hover:bg-cyan-500">Submit Request</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- INSTALLATION MODAL --- */}
      {isInstallModalOpen && selectedOrder && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-charcoal-900 border border-charcoal-700 rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden">
            <div className="flex justify-between items-center p-5 border-b border-charcoal-800 bg-charcoal-800/30">
              <h2 className="text-lg font-bold text-white flex items-center">
                <CheckCircle className="mr-2 text-lime-400" /> Complete Installation: {selectedOrder.customer_name}
              </h2>
              <button onClick={() => setIsInstallModalOpen(false)} className="text-gray-400 hover:text-white"><X size={20} /></button>
            </div>
            <form onSubmit={handleCompleteInstall} className="p-6 space-y-6">
              <div className="grid grid-cols-2 gap-6">
                <div><label className="block text-sm font-medium text-gray-300 mb-2">Flexscan Result (dBm)</label><input type="number" step="0.1" required value={flexscanDbm} onChange={(e) => setFlexscanDbm(e.target.value)} className="w-full bg-charcoal-800 border border-charcoal-700 rounded-lg p-2.5 text-white" placeholder="e.g. -24.2" /></div>
                <div className="flex items-center mt-8"><input type="checkbox" required checked={checklistCompleted} onChange={(e) => setChecklistCompleted(e.target.checked)} className="w-5 h-5 rounded border-charcoal-700 text-cyan-500 bg-charcoal-800" /><label className="ml-3 text-sm font-medium text-gray-300">All Quality Checklists Completed</label></div>
              </div>
              <div className="border-t border-charcoal-800 pt-5">
                <h3 className="text-sm font-semibold text-white mb-4">Required Installation Photos</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div><label className="block text-xs text-gray-400 mb-1">NAP Photo</label><input type="file" required onChange={(e) => setFiles(p => ({...p, photo_nap: e.target.files[0]}))} className="text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-cyan-900/30 file:text-cyan-400 hover:file:bg-cyan-900/50"/></div>
                  <div><label className="block text-xs text-gray-400 mb-1">Routing Photo</label><input type="file" required onChange={(e) => setFiles(p => ({...p, photo_routing: e.target.files[0]}))} className="text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-cyan-900/30 file:text-cyan-400 hover:file:bg-cyan-900/50"/></div>
                  <div><label className="block text-xs text-gray-400 mb-1">Rosette Photo</label><input type="file" required onChange={(e) => setFiles(p => ({...p, photo_rosette: e.target.files[0]}))} className="text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-cyan-900/30 file:text-cyan-400 hover:file:bg-cyan-900/50"/></div>
                  <div><label className="block text-xs text-gray-400 mb-1">Flexscan Screen</label><input type="file" required onChange={(e) => setFiles(p => ({...p, photo_flexscan: e.target.files[0]}))} className="text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-cyan-900/30 file:text-cyan-400 hover:file:bg-cyan-900/50"/></div>
                </div>
              </div>
              <div className="flex justify-end pt-4 border-t border-charcoal-800 space-x-3">
                <button type="button" onClick={() => setIsInstallModalOpen(false)} className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-300 hover:bg-charcoal-800 transition-colors">Cancel</button>
                <button type="submit" className="px-4 py-2 rounded-lg text-sm font-semibold bg-cyan-600 text-white hover:bg-cyan-500 transition-colors flex items-center">Submit & Generate PDF</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default FTTHProvisioning;