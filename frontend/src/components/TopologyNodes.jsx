import React from 'react';
import { Handle, Position } from 'reactflow';
import { Server, Share2, Home } from 'lucide-react';

// 1. Core / OLT Node (Cyan Glow)
export const CoreNode = ({ data }) => {
  return (
    <div className="bg-charcoal-800 border-2 border-cyan-500 rounded-lg p-3 shadow-cyan-glow flex items-center min-w-[220px]">
      <div className="bg-cyan-500/20 p-2 rounded-md mr-3">
        <Server className="text-cyan-400" size={24} />
      </div>
      <div>
        <div className="text-[10px] text-cyan-400 font-bold uppercase tracking-widest">{data.type || 'CORE / OLT'}</div>
        <div className="text-white font-medium text-sm">{data.label}</div>
      </div>
      {/* Connection Ports */}
      <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-cyan-500 border-2 border-charcoal-900" />
    </div>
  );
};

// 2. Cable / Splitter Node (Lime Glow)
export const SplitterNode = ({ data }) => {
  return (
    <div className="bg-charcoal-800 border-2 border-lime-500 rounded-lg p-3 shadow-lime-glow flex items-center min-w-[220px]">
      <div className="bg-lime-500/20 p-2 rounded-md mr-3">
        <Share2 className="text-lime-400" size={24} />
      </div>
      <div>
        <div className="text-[10px] text-lime-400 font-bold uppercase tracking-widest">{data.type || 'FIBER / SPLITTER'}</div>
        <div className="text-white font-medium text-sm">{data.label}</div>
      </div>
      <Handle type="target" position={Position.Top} className="w-3 h-3 bg-lime-500 border-2 border-charcoal-900" />
      <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-lime-500 border-2 border-charcoal-900" />
    </div>
  );
};

// 3. Customer / ONT Node (Slate/White)
export const CustomerNode = ({ data }) => {
  return (
    <div className="bg-charcoal-700 border-2 border-gray-400 rounded-lg p-3 flex items-center min-w-[220px]">
      <div className="bg-gray-600 p-2 rounded-md mr-3">
        <Home className="text-white" size={24} />
      </div>
      <div>
        <div className="text-[10px] text-gray-300 font-bold uppercase tracking-widest">{data.type || 'CUSTOMER / ONT'}</div>
        <div className="text-white font-medium text-sm">{data.label}</div>
      </div>
      <Handle type="target" position={Position.Top} className="w-3 h-3 bg-gray-400 border-2 border-charcoal-900" />
    </div>
  );
};