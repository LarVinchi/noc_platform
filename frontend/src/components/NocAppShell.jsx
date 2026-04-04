import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Map, Users, AlertTriangle, Settings } from 'lucide-react';

const NocAppShell = ({ children }) => {
  return (
    <div className="flex h-screen w-screen bg-charcoal-900 text-white overflow-hidden">
      
      {/* Sidebar Navigation */}
      <nav className="w-64 bg-charcoal-800 border-r border-charcoal-700 flex flex-col">
        {/* Brand Header */}
        <div className="h-16 flex items-center px-6 border-b border-charcoal-700">
          <div className="w-3 h-3 rounded-full bg-cyan-400 shadow-cyan-glow mr-3"></div>
          <h1 className="text-xl font-bold tracking-wider text-cyan-400">NOC<span className="text-white">OS</span></h1>
        </div>

        {/* Navigation Links */}
        <div className="flex-1 py-6 px-4 space-y-2">
          <NavItem to="/" icon={<LayoutDashboard size={20} />} label="Dashboard" />
          <NavItem to="/topology" icon={<Map size={20} />} label="Topology Map" />
          <NavItem to="/crm" icon={<Users size={20} />} label="CRM & Services" />
          <NavItem to="/incidents" icon={<AlertTriangle size={20} />} label="Incidents" />
        </div>

        {/* Footer/Settings */}
        <div className="p-4 border-t border-charcoal-700">
          <NavItem to="/settings" icon={<Settings size={20} />} label="Settings" />
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <header className="h-16 border-b border-charcoal-700 flex items-center justify-between px-8 bg-charcoal-800/50 backdrop-blur-sm">
          <h2 className="text-lg font-medium text-gray-200">Global Overview</h2>
          <div className="flex items-center space-x-4">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-lime-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-lime-500 shadow-lime-glow"></span>
            </span>
            <span className="text-sm text-gray-400">System Online</span>
          </div>
        </header>

        <div className="flex-1 overflow-auto p-8">
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
      className={({ isActive }) => `
        w-full flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200
        ${isActive 
          ? 'bg-charcoal-700 text-cyan-400 border-l-4 border-cyan-400' 
          : 'text-gray-400 hover:bg-charcoal-700 hover:text-gray-200 border-l-4 border-transparent'
        }
      `}
    >
      {icon}
      <span className="font-medium">{label}</span>
    </NavLink>
  );
};

export default NocAppShell;