import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import apiClient from '../src/api/client.js';
import '../src/index.css';
import './demo.css';
import DemoApp from './DemoApp.jsx';
import { openDemoSession, wasOpened } from './session.js';

apiClient.defaults.baseURL = '/api';

const initialIdentity = wasOpened() ? await openDemoSession().catch(() => null) : null;

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <DemoApp initialIdentity={initialIdentity} />
  </StrictMode>,
);
