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
import apiClient from '../api/client'; // Import your Axios client

import { CoreNode, SplitterNode, CustomerNode } from '../components/TopologyNodes';
import { Activity } from 'lucide-react';

const TopologyMap = () => {
  const nodeTypes = useMemo(() => ({
    core: CoreNode,
    splitter: SplitterNode,
    customer: CustomerNode,
  }), []);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);

  // Fetch the topology data from FastAPI on load
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

  if (loading) {
    return (
      <div className="h-full w-full flex items-center justify-center text-cyan-400">
        <Activity className="animate-spin mr-3" size={32} />
        <span className="text-xl">Mapping Network Infrastructure...</span>
      </div>
    );
  }

  return (
    <div className="h-full w-full flex flex-col space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-semibold text-white">Network Topology Viewer</h2>
        <div className="flex space-x-2 bg-charcoal-800 p-1 rounded-lg border border-charcoal-700">
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
          fitView
          fitViewOptions={{ padding: 0.2 }}
        >
          <Background color="#334155" gap={16} size={1} />
          <Controls className="bg-charcoal-800 fill-white border-charcoal-700" />
          <MiniMap 
            nodeColor={(n) => {
              if (n.type === 'core') return '#06b6d4';
              if (n.type === 'splitter') return '#84cc16';
              return '#94a3b8';
            }}
            maskColor="rgba(15, 23, 42, 0.7)"
            className="bg-charcoal-800 border-charcoal-700"
          />
        </ReactFlow>
      </div>
    </div>
  );
};

export default TopologyMap;