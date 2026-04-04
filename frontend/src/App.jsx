import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import NocAppShell from './components/NocAppShell';
import CrmServices from './pages/CrmServices';
import TopologyMap from './pages/TopologyMap';

// Extract the dashboard into a quick local component
const DashboardHome = () => (
  <div className="grid grid-cols-3 gap-6">
    <div className="bg-charcoal-800 p-6 rounded-xl border border-charcoal-700">
      <h3 className="text-gray-400 text-sm mb-2">Active Services</h3>
      <p className="text-3xl font-bold text-white">1,204</p>
    </div>
    <div className="bg-charcoal-800 p-6 rounded-xl border border-charcoal-700">
      <h3 className="text-gray-400 text-sm mb-2">Open Incidents</h3>
      <p className="text-3xl font-bold text-cyan-400">3</p>
    </div>
    <div className="bg-charcoal-800 p-6 rounded-xl border border-charcoal-700">
      <h3 className="text-gray-400 text-sm mb-2">Network Health</h3>
      <p className="text-3xl font-bold text-lime-400">99.9%</p>
    </div>
  </div>
);

function App() {
  return (
    <BrowserRouter>
      <NocAppShell>
        <Routes>
          <Route path="/" element={<DashboardHome />} />
          <Route path="/crm" element={<CrmServices />} />
          {/* We will build these later */}
          <Route path="/topology" element={<TopologyMap />} />
          <Route path="/incidents" element={<div className="text-white">Incidents Kanban Coming Soon</div>} />
        </Routes>
      </NocAppShell>
    </BrowserRouter>
  );
}

export default App;