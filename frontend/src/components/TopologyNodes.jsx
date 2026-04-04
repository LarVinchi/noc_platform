import React from 'react';
import { Handle, Position } from 'reactflow';
import { Router, GitMerge, Box, Server, Building2, Home } from 'lucide-react';

// Base Node to keep styling consistent and DRY
// Added 'badge' prop and 'relative' class for port/core numbers
const BaseNode = ({ label, type, badge, icon: Icon, textClass, bgClass, borderClass, handleClass, shadowClass, isTarget = true, isSource = true }) => (
  <div className={`relative bg-charcoal-800 border-2 ${borderClass} rounded-lg p-3 ${shadowClass || 'shadow-md'} flex items-center min-w-[220px]`}>
    
    {/* NEW: Optional Badge for Port Numbers or Core Counts */}
    {badge && (
      <div className={`absolute -top-3 -right-2 px-2 py-0.5 text-[10px] font-bold tracking-wider uppercase rounded-md bg-[#0f172a] border-2 ${borderClass} ${textClass} shadow-lg z-10`}>
        {badge}
      </div>
    )}

    <div className={`${bgClass} p-2 rounded-md mr-3`}>
      <Icon className={textClass} size={24} />
    </div>
    <div className="flex flex-col">
      <div className={`text-[10px] ${textClass} font-bold uppercase tracking-widest`}>
        {type}
      </div>
      <div className="text-white font-medium text-sm pr-2">{label}</div>
    </div>

    {/* Connection Ports - Horizontal Left to Right Flow */}
    {isTarget && (
      <Handle type="target" position={Position.Left} className={`w-3 h-3 ${handleClass} border-2 border-charcoal-900`} />
    )}
    {isSource && (
      <Handle type="source" position={Position.Right} className={`w-3 h-3 ${handleClass} border-2 border-charcoal-900`} />
    )}
  </div>
);

// 1. Core / Route Node (Cyan Glow)
export const CoreNode = ({ data }) => (
  <BaseNode 
    label={data.label} 
    type={data.type || 'CORE'} 
    badge={data.badge} // Pass badge data down
    icon={Router} 
    textClass="text-cyan-400"
    bgClass="bg-cyan-500/20"
    borderClass="border-cyan-500"
    handleClass="bg-cyan-500"
    shadowClass="shadow-cyan-glow"
    isTarget={false} 
  />
);

// 2. Cable Node (Green Styling)
export const CableNode = ({ data }) => (
  <BaseNode 
    label={data.label} 
    type={data.type || 'CABLE'} 
    badge={data.badge}
    icon={Server} 
    textClass="text-green-400"
    bgClass="bg-green-500/20"
    borderClass="border-green-500"
    handleClass="bg-green-500"
    shadowClass="shadow-green-glow" 
  />
);

// 3. Splitter / NAP Node (Purple Styling)
export const SplitterNode = ({ data }) => {
  const Icon = data.type === 'NAP' ? Box : GitMerge;
  return (
    <BaseNode 
      label={data.label} 
      type={data.type || 'SPLITTER'} 
      badge={data.badge}
      icon={Icon} 
      textClass="text-purple-400"
      bgClass="bg-purple-500/20"
      borderClass="border-purple-500"
      handleClass="bg-purple-500"
      shadowClass="shadow-purple-glow" 
    />
  );
};

// 4. Customer / ONT Node (Orange Styling)
export const CustomerNode = ({ data }) => {
  const Icon = (data.type === 'DIA' || data.type === 'DARKFIBER') ? Building2 : Home;
  return (
    <BaseNode 
      label={data.label} 
      type={data.type || 'CUSTOMER'} 
      badge={data.badge}
      icon={Icon} 
      textClass="text-orange-400"
      bgClass="bg-orange-500/20"
      borderClass="border-orange-500"
      handleClass="bg-orange-500"
      shadowClass="shadow-orange-glow" 
      isSource={false} 
    />
  );
};