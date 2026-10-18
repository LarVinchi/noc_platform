import { Routes, Route, Link } from 'react-router-dom';
import CrmServices from '../pages/CrmServices';
import NetworkTopology from '../pages/NetworkTopology';
import FTTHProvisioning from '../pages/FTTHProvisioning';
import IncidentManagement from '../pages/IncidentManagement';
import OperationsDashboard from '../pages/OperationsDashboard';
import AuditHistory from '../pages/AuditHistory';
import Monitoring from '../pages/Monitoring';
import ResponseCenter from '../pages/ResponseCenter';
import Documents from '../pages/Documents';
import FtthOperations from '../pages/FtthOperations';
import MailTriage from '../pages/MailTriage';
import Knowledge from '../pages/Knowledge';
import EnergyOperations from '../pages/EnergyOperations';
import ServerHealth from '../pages/ServerHealth';
import { EmptyState } from './WorkspaceUI';

export default function NocRoutes({ identity }) {
  return <Routes>
    <Route path="/" element={<OperationsDashboard />} />
    <Route path="/crm" element={<CrmServices identity={identity} />} />
    <Route path="/topology" element={<NetworkTopology />} />
    <Route path="/provisioning" element={<FTTHProvisioning identity={identity} />} />
    <Route path="/incidents" element={<IncidentManagement identity={identity} />} />
    <Route path="/response" element={<ResponseCenter identity={identity} />} />
    <Route path="/documents" element={<Documents identity={identity} />} />
    <Route path="/ftth-operations" element={<FtthOperations identity={identity} />} />
    <Route path="/mail" element={<MailTriage identity={identity} />} />
    <Route path="/knowledge" element={<Knowledge />} />
    <Route path="/audit" element={<AuditHistory />} />
    <Route path="/energy" element={<EnergyOperations identity={identity} />} />
    <Route path="/server-health" element={<ServerHealth identity={identity} />} />
    <Route path="/monitoring" element={<Monitoring identity={identity} />} />
    <Route path="*" element={<EmptyState title="Workspace not found"><Link to="/">Return to operations overview</Link></EmptyState>} />
  </Routes>;
}
