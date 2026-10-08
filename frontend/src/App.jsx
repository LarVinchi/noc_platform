import React, { useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import NocAppShell from './components/NocAppShell';
import CrmServices from './pages/CrmServices';
import TopologyMap from './pages/TopologyMap';
import FTTHProvisioning from './pages/FTTHProvisioning';
import IncidentManagement from './pages/IncidentManagement';
import OperationsDashboard from './pages/OperationsDashboard';
import NOCLoginScreen from './pages/NOCLoginScreen'; // <-- IMPORT NEW SPLIT-SCREEN LOGIN

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
          <Route path="/" element={<OperationsDashboard />} />
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