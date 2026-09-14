import React, { useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import NocAppShell from './components/NocAppShell';
import CrmServices from './pages/CrmServices';
import TopologyMap from './pages/TopologyMap';
import FTTHProvisioning from './pages/FTTHProvisioning';
import IncidentManagement from './pages/IncidentManagement';
import NOCLoginScreen from './pages/NOCLoginScreen'; // <-- IMPORT NEW SPLIT-SCREEN LOGIN

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
  // Authentication State
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // 1. If not authenticated, show the interactive NOC Login Screen.
  // The Login Screen handles the animation internally and calls onLoginSuccess when done.
  if (!isAuthenticated) {
    return <NOCLoginScreen onLoginSuccess={() => setIsAuthenticated(true)} />;
  }

  // 2. Authentication complete! Load the full NOC OS Routing Shell
  return (
    <BrowserRouter>
      <NocAppShell>
        <Routes>
          <Route path="/" element={<DashboardHome />} />
          <Route path="/crm" element={<CrmServices />} />
          <Route path="/topology" element={<TopologyMap />} />
          <Route path="/provisioning" element={<FTTHProvisioning />} />
          <Route path="/incidents" element={<IncidentManagement />} />
        </Routes>
      </NocAppShell>
    </BrowserRouter>
  );
}

export default App;