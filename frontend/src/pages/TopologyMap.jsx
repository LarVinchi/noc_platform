import React, { useCallback, useMemo, useState, useEffect } from 'react';
import ReactFlow, { 
  MiniMap, 
  Controls, 
  Background, 
  useNodesState, 
  useEdgesState,
  addEdge
} from 'reactflow';
import 'reactflow/dist/style.css';
import apiClient from '../api/client'; 

import { CoreNode, CableNode, SplitterNode, CustomerNode } from '../components/TopologyNodes';
import { Activity, X, Info, Activity as ActivityIcon, MapPin, Hash } from 'lucide-react';

const TopologyMap = () => {
  const nodeTypes = useMemo(() => ({
    core: CoreNode,
    cable: CableNode,
    splitter: SplitterNode,
    customer: CustomerNode,
  }), []);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  
  // NEW: State to track which node the user clicked
  const [selectedNode, setSelectedNode] = useState(null);

  useEffect(() => {
    apiClient.get('/topology/')
      .then((response) => {
        setNodes(response.data.nodes);
        setEdges(response.data.edges);
        setLoading(false);
      })
      .catch((error) => {
        console.error("Error fetching topology:", error);
        setLoading(false);
      });
  }, [setNodes, setEdges]);

  const onConnect = useCallback((params) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  // NEW: Handler for when a node is clicked
  const onNodeClick = useCallback((event, node) => {
    setSelectedNode(node);
  }, []);

  // NEW: Handler to close the sidebar
  const closeSidebar = () => {
    setSelectedNode(null);
  };

  if (loading) {
    return (
      <div className="h-full w-full flex items-center justify-center text-cyan-400">
        <Activity className="animate-spin mr-3" size={32} />
        <span className="text-xl">Mapping Network Infrastructure...</span>
      </div>
    );
  }

  return (
    <div className="h-full w-full flex flex-col space-y-4 relative overflow-hidden">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-semibold text-white">Network Topology Viewer</h2>
        <div className="flex space-x-2 bg-charcoal-800 p-1 rounded-lg border border-charcoal-700 z-10">
          <button className="px-4 py-1 text-sm rounded bg-charcoal-700 text-cyan-400">Logical Schematic</button>
          <button className="px-4 py-1 text-sm rounded text-gray-400 hover:text-white cursor-not-allowed" title="Requires GIS Module">Physical GIS Map</button>
        </div>
      </div>

      <div className="flex-1 bg-charcoal-900 border border-charcoal-700 rounded-xl overflow-hidden relative shadow-inner">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick} // <-- Attached the click handler here
          fitView
          fitViewOptions={{ padding: 0.2 }}
        >
          <Background color="#334155" gap={16} size={1} />
          <Controls className="bg-charcoal-800 fill-white border-charcoal-700" />
          <MiniMap 
            nodeColor={(n) => {
              if (n.type === 'core') return '#06b6d4';
              if (n.type === 'cable') return '#22c55e';
              if (n.type === 'splitter') return '#a855f7';
              if (n.type === 'customer') return '#f97316';
              return '#94a3b8';
            }}
            maskColor="rgba(15, 23, 42, 0.7)"
            className="bg-charcoal-800 border-charcoal-700"
          />
        </ReactFlow>

        {/* NEW: The Slide-Out Sidebar */}
        {selectedNode && (
          <div className="absolute top-0 right-0 w-80 h-full bg-charcoal-800 border-l border-charcoal-700 shadow-2xl z-50 flex flex-col animate-slide-in-right">
            
            {/* Sidebar Header */}
            <div className="p-4 border-b border-charcoal-700 flex justify-between items-center bg-[#0f172a]">
              <div className="flex items-center space-x-2">
                <Info className="text-cyan-400" size={20} />
                <h3 className="text-lg font-bold text-white tracking-wide">
                  {selectedNode.data?.label || 'Node Details'}
                </h3>
              </div>
              <button onClick={closeSidebar} className="text-gray-400 hover:text-white transition-colors">
                <X size={24} />
              </button>
            </div>

            {/* Sidebar Content Body */}
            <div className="p-4 flex-1 overflow-y-auto text-sm space-y-4">
              
              {/* Type Card */}
              <div className="bg-charcoal-900 p-3 rounded-lg border border-charcoal-700">
                <div className="flex items-center text-gray-400 mb-1">
                  <Hash size={14} className="mr-1" />
                  <span className="text-xs uppercase tracking-wider">Node Type</span>
                </div>
                <div className="font-semibold text-white capitalize">{selectedNode.type}</div>
              </div>

              {/* Dynamic Badge/Port Card */}
              {selectedNode.data?.badge && (
                <div className="bg-charcoal-900 p-3 rounded-lg border border-charcoal-700">
                  <div className="flex items-center text-gray-400 mb-1">
                    <MapPin size={14} className="mr-1" />
                    <span className="text-xs uppercase tracking-wider">Port / Core Allocation</span>
                  </div>
                  <div className="font-semibold text-cyan-400">{selectedNode.data.badge}</div>
                </div>
              )}

              {/* Hardcoded Status (Will be dynamic in Option 2) */}
              <div className="bg-charcoal-900 p-3 rounded-lg border border-charcoal-700">
                <div className="flex items-center text-gray-400 mb-1">
                  <ActivityIcon size={14} className="mr-1" />
                  <span className="text-xs uppercase tracking-wider">Current Status</span>
                </div>
                <div className="font-semibold text-green-400 flex items-center">
                  <span className="w-2 h-2 rounded-full bg-green-500 mr-2 animate-pulse"></span> 
                  Online & Active
                </div>
              </div>

              {/* Placeholder for future Database stats */}
              <div className="mt-6 p-4 rounded bg-charcoal-900/50 border border-dashed border-charcoal-700 text-center text-gray-500 text-xs">
                Additional telemetry, routing details, and live bandwidth stats will populate here when wired to PostgreSQL.
              </div>

            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TopologyMap;