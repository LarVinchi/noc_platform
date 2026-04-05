import React from 'react';
import { Handle, Position } from 'reactflow';
import { Server, Share2, Home, GitMerge } from 'lucide-react';

const BaseNode = ({ data, icon: Icon, color, isOnline = true }) => {
  return (
    <div 
      className="relative bg-charcoal-900 border border-charcoal-700 rounded-lg shadow-xl min-w-[240px] flex items-center p-3 transition-transform hover:scale-105 hover:border-gray-500 hover:shadow-2xl"
      style={{ borderLeft: `4px solid ${color}` }}
    >
      {/* Input Port */}
      <Handle type="target" position={Position.Left} className="w-3 h-3 bg-charcoal-600 border-2 border-charcoal-900" />
      
      {/* Icon Box */}
      <div className="flex-shrink-0 bg-charcoal-950 p-2.5 rounded-md border border-charcoal-800 mr-3">
        <Icon size={22} color={color} />
      </div>
      
      {/* Labels */}
      <div className="flex flex-col flex-grow pr-4">
        <span className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">{data.type || 'Network Node'}</span>
        <span className="text-sm font-bold text-gray-100 mt-0.5 truncate">{data.label}</span>
        {data.badge && (
          <span className="text-xs font-mono text-gray-400 bg-charcoal-800 px-1.5 py-0.5 rounded mt-1 inline-block w-max">
            {data.badge}
          </span>
        )}
      </div>

      {/* Glowing Status Dot */}
      <div className="absolute top-2.5 right-2.5" title={isOnline ? "Operational" : "Offline"}>
        {isOnline ? (
          <span className="flex w-2.5 h-2.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.8)] animate-pulse"></span>
        ) : (
          <span className="flex w-2.5 h-2.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"></span>
        )}
      </div>

      {/* Output Port */}
      <Handle type="source" position={Position.Right} className="w-3 h-3 bg-charcoal-600 border-2 border-charcoal-900" />
    </div>
  );
};

// Map different node types to specific icons and colors
export const CoreNode = (props) => <BaseNode {...props} icon={Server} color="#3b82f6" />; // Blue
export const CableNode = (props) => <BaseNode {...props} icon={GitMerge} color="#8b5cf6" />; // Purple
export const SplitterNode = (props) => <BaseNode {...props} icon={Share2} color="#f97316" />; // Orange
export const CustomerNode = (props) => <BaseNode {...props} icon={Home} color="#10b981" />; // Green