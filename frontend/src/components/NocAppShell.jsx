import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { LayoutDashboard, Map, Users, AlertTriangle, HardHat } from 'lucide-react';

const pageNames = { '/': 'Operations overview', '/topology': 'Network topology', '/crm': 'Customers and services', '/provisioning': 'FTTH provisioning', '/incidents': 'Incident management' };
const NocAppShell = ({ children }) => {
  const { pathname } = useLocation();
  return (
    <div className="flex h-screen w-screen bg-charcoal-900 text-white overflow-hidden">
      
      {/* Sidebar Navigation */}
      <nav aria-label="Main navigation" className="w-16 md:w-64 shrink-0 bg-charcoal-800 border-r border-charcoal-700 flex flex-col">
        {/* Brand Header */}
        <div className="h-16 flex items-center px-3 md:px-6 border-b border-charcoal-700">
          <div className="w-3 h-3 shrink-0 rounded-full bg-cyan-400 md:mr-3"></div>
          <h1 className="hidden md:block text-xl font-bold tracking-wider text-cyan-400">NOC<span className="text-white">OS</span></h1>
        </div>

        {/* Navigation Links */}
        <div className="flex-1 py-6 px-4 space-y-2">
          <NavItem to="/" icon={<LayoutDashboard size={20} />} label="Dashboard" />
          <NavItem to="/topology" icon={<Map size={20} />} label="Topology Map" />
          <NavItem to="/crm" icon={<Users size={20} />} label="CRM & Services" />
          
          {/* NEW PROVISIONING LINK */}
          <NavItem to="/provisioning" icon={<HardHat size={20} />} label="FTTH Provisioning" />
          
          <NavItem to="/incidents" icon={<AlertTriangle size={20} />} label="Incidents" />
        </div>

        {/* Footer/Settings */}
        <div className="p-4 border-t border-charcoal-700">
          <span className="hidden md:block text-xs text-slate-500">AFL · Network operations</span>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 flex flex-col overflow-hidden relative">
        <header className="h-16 border-b border-charcoal-700 flex items-center justify-between px-8 bg-charcoal-800/50 backdrop-blur-sm">
          <h2 className="text-lg font-medium text-gray-200">{pageNames[pathname] || "NOC workspace"}</h2>
          <span className="text-xs text-slate-400">Operator workspace</span>
        </header>

        <div className="flex-1 overflow-auto p-4 md:p-8">
          {children}
        </div>
      </main>
    </div>
  );
};

// Updated: Now uses NavLink for actual routing
const NavItem = ({ to, icon, label }) => {
  return (
    <NavLink 
      to={to}
      end={to === "/"}
      title={label}
      aria-label={label}
      className={({ isActive }) => `
        w-full flex items-center space-x-0 md:space-x-3 px-2 md:px-4 py-3 rounded-lg transition-all duration-200
        ${isActive 
          ? 'bg-charcoal-700 text-cyan-400 border-l-4 border-cyan-400' 
          : 'text-gray-400 hover:bg-charcoal-700 hover:text-gray-200 border-l-4 border-transparent'
        }
      `}
    >
      {icon}
      <span className="hidden md:inline font-medium">{label}</span>
    </NavLink>
  );
};

export default NocAppShell;
