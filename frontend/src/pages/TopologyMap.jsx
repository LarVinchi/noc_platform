import React, { useCallback } from 'react';
import ReactFlow, { 
  MiniMap, 
  Controls, 
  Background, 
  useNodesState, 
  useEdgesState,
  addEdge
} from 'reactflow';
import 'reactflow/dist/style.css';

// Initial placeholder data (We will replace this with your DB data later!)
const initialNodes = [
  { id: 'core-1', position: { x: 250, y: 50 }, data: { label: 'Core Router (Data Center)' }, style: { background: '#1e293b', color: '#22d3ee', border: '1px solid #06b6d4', borderRadius: '8px', padding: '10px' } },
  { id: 'cable-1', position: { x: 250, y: 150 }, data: { label: '48-Core Fiber (Main Trunk)' }, style: { background: '#1e293b', color: '#a3e635', border: '1px solid #84cc16', borderRadius: '8px', padding: '10px' } },
  { id: 'cust-1', position: { x: 100, y: 250 }, data: { label: 'Cupcake (Customer)' }, style: { background: '#334155', color: '#fff', border: '1px solid #475569', borderRadius: '8px', padding: '10px' } },
  { id: 'cust-2', position: { x: 400, y: 250 }, data: { label: 'SwiftNet (Customer)' }, style: { background: '#334155', color: '#fff', border: '1px solid #475569', borderRadius: '8px', padding: '10px' } },
];

const initialEdges = [
  { id: 'e1-2', source: 'core-1', target: 'cable-1', animated: true, style: { stroke: '#06b6d4', strokeWidth: 2 } },
  { id: 'e2-3', source: 'cable-1', target: 'cust-1', animated: true, style: { stroke: '#84cc16', strokeWidth: 2 } },
  { id: 'e2-4', source: 'cable-1', target: 'cust-2', animated: true, style: { stroke: '#84cc16', strokeWidth: 2 } },
];

const TopologyMap = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback((params) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  return (
    <div className="h-full w-full flex flex-col space-y-4">
      
      {/* Top Control Bar matching your design */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-semibold text-white">Network Topology Viewer</h2>
        <div className="flex space-x-2 bg-charcoal-800 p-1 rounded-lg border border-charcoal-700">
          <button className="px-4 py-1 text-sm rounded bg-charcoal-700 text-cyan-400">Logical Schematic</button>
          <button className="px-4 py-1 text-sm rounded text-gray-400 hover:text-white">Physical GIS Map</button>
        </div>
      </div>

      {/* The Actual Interactive Map Canvas */}
      <div className="flex-1 bg-charcoal-900 border border-charcoal-700 rounded-xl overflow-hidden relative shadow-inner">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
        >
          {/* Adds grid dots in the background */}
          <Background color="#334155" gap={16} size={1} />
          {/* Zoom & Pan controls */}
          <Controls className="bg-charcoal-800 fill-white border-charcoal-700" />
          {/* Small overview map in the corner */}
          <MiniMap 
            nodeColor={(n) => {
              if (n.id.includes('core')) return '#06b6d4';
              if (n.id.includes('cable')) return '#84cc16';
              return '#475569';
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