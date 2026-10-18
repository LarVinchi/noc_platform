import React, { useState, useEffect } from 'react';
import { BrowserRouter } from 'react-router-dom';
import NocAppShell from './components/NocAppShell';
import NocRoutes from './components/NocRoutes';
import NOCLoginScreen from './pages/NOCLoginScreen'; // <-- IMPORT NEW SPLIT-SCREEN LOGIN
import { initializeAuth, accessToken, signIn, signOut } from './api/auth';
import { setTokenProvider } from './api/client';

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
  return <BrowserRouter><NocAppShell identity={identity} onLogout={async () => { await signOut(); setIdentity(null); }}><NocRoutes identity={identity} /></NocAppShell></BrowserRouter>;
}
export default App;
