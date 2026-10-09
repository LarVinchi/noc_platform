import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import NocAppShell from './components/NocAppShell';
import CrmServices from './pages/CrmServices';
import NetworkTopology from './pages/NetworkTopology';
import FTTHProvisioning from './pages/FTTHProvisioning';
import IncidentManagement from './pages/IncidentManagement';
import OperationsDashboard from './pages/OperationsDashboard';
import NOCLoginScreen from './pages/NOCLoginScreen'; // <-- IMPORT NEW SPLIT-SCREEN LOGIN
import { initializeAuth, accessToken, signIn, signOut } from './api/auth';
import { setTokenProvider } from './api/client';
import AuditHistory from './pages/AuditHistory';
import Monitoring from './pages/Monitoring';
import ResponseCenter from './pages/ResponseCenter';
import Documents from './pages/Documents';

function App() {
  // Authentication State
  const [identity, setIdentity] = useState(null);
  const [configuration, setConfiguration] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    initializeAuth().then(config => {
      setConfiguration(config); setTokenProvider(accessToken);
    }).catch(() => setError('Unable to initialize access. Check that the API is running and identity configuration is valid.'));
  }, []);

  // 1. If not authenticated, show the interactive NOC Login Screen.
  // The Login Screen handles the animation internally and calls onLoginSuccess when done.
  if (!identity) {
    return <NOCLoginScreen configuration={configuration} error={error} onLogin={async () => setIdentity(await signIn())} />;
  }

  // 2. Authentication complete! Load the full NOC OS Routing Shell
  return (
    <BrowserRouter>
      <NocAppShell identity={identity} onLogout={async () => { await signOut(); setIdentity(null); }}>
        <Routes>
          <Route path="/" element={<OperationsDashboard />} />
          <Route path="/crm" element={<CrmServices />} />
          <Route path="/topology" element={<NetworkTopology />} />
          <Route path="/provisioning" element={<FTTHProvisioning />} />
          <Route path="/incidents" element={<IncidentManagement identity={identity} />} />
          <Route path="/response" element={<ResponseCenter identity={identity} />} />
          <Route path="/documents" element={<Documents identity={identity} />} />
          <Route path="/audit" element={<AuditHistory />} />
          <Route path="/monitoring" element={<Monitoring identity={identity} />} />
        </Routes>
      </NocAppShell>
    </BrowserRouter>
  );
}

export default App;
