import React, { useCallback, useMemo, useState, useEffect } from 'react';
import ReactFlow, { 
  MiniMap, 
  Controls, 
  Background, 
  useNodesState, 
  useEdgesState,
  addEdge
} from 'reactflow';
import dagre from 'dagre';
import 'reactflow/dist/style.css';
import apiClient from '../api/client'; 

import { CoreNode, CableNode, SplitterNode, CustomerNode } from '../components/TopologyNodes';
import { Activity, X, Info, Activity as ActivityIcon, MapPin, Hash, Search, Eye } from 'lucide-react';

// --- Dagre Auto-Layout Configuration ---
const getLayoutedElements = (nodes, edges, direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  
  dagreGraph.setGraph({ rankdir: direction, ranksep: 250, nodesep: 100 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 280, height: 100 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      targetPosition: 'left',
      sourcePosition: 'right',
      position: {
        x: nodeWithPosition.x - 140, 
        y: nodeWithPosition.y - 50,
      },
    };
  });

  return { layoutedNodes, layoutedEdges: edges };
};

const TopologyMap = () => {
  const nodeTypes = useMemo(() => ({
    core: CoreNode, cable: CableNode, primary_splitter: SplitterNode, secondary_splitter: SplitterNode,
    access_point: SplitterNode, cpe_outlet: CustomerNode, dia_endpoint: CustomerNode,
    dark_fiber_endpoint: CustomerNode, layer2_endpoint: CustomerNode,
  }), []);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  
  const [selectedNode, setSelectedNode] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [rfInstance, setRfInstance] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  
  const [contextMenu, setContextMenu] = useState(null);

  useEffect(() => {
    apiClient.get('/topology/')
      .then((response) => {
        const { layoutedNodes, layoutedEdges } = getLayoutedElements(response.data.nodes, response.data.edges);
        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
        setLoading(false);
        setTimeout(() => rfInstance?.fitView({ padding: 0.2, duration: 800 }), 100);
      })
      .catch((error) => {
        console.error("Error fetching topology:", error);
        setLoading(false);
      });
  }, [setNodes, setEdges, rfInstance]);

  // BFS Path Tracing for Search
  useEffect(() => {
    if (!rfInstance) return;
    const query = searchQuery.trim().toLowerCase();

    setNodes((nds) => {
      const currentEdges = rfInstance.getEdges();
      
      if (!query) return nds.map(n => ({ ...n, style: { opacity: 1, filter: 'none', transform: 'scale(1)' } }));

      const exactMatches = new Set();
      nds.forEach(n => {
        if (n.data?.label?.toLowerCase().includes(query) || n.data?.type?.toLowerCase().includes(query)) {
          exactMatches.add(n.id);
        }
      });

      const highlightedNodes = new Set(exactMatches);
      let queue = Array.from(exactMatches);

      while(queue.length > 0) {
        const curr = queue.shift();
        currentEdges.forEach(e => {
          if (e.source === curr && !highlightedNodes.has(e.target)) {
            highlightedNodes.add(e.target); queue.push(e.target);
          }
          if (e.target === curr && !highlightedNodes.has(e.source)) {
            highlightedNodes.add(e.source); queue.push(e.source);
          }
        });
      }

      return nds.map(n => {
        const isExact = exactMatches.has(n.id);
        const isPath = highlightedNodes.has(n.id);
        return {
          ...n,
          style: {
            opacity: isPath ? 1 : 0.15,
            filter: isPath ? 'none' : 'grayscale(100%)',
            boxShadow: isExact ? '0 0 20px 4px rgba(34, 211, 238, 0.8)' : 'none',
            transform: isExact ? 'scale(1.05)' : 'scale(1)',
            transition: 'all 0.3s ease',
            zIndex: isExact ? 100 : (isPath ? 50 : 0)
          }
        };
      });
    });

    setEdges((eds) => {
      if (!query) return eds.map(e => ({ ...e, style: { opacity: 1 }, animated: true }));
      const nds = rfInstance.getNodes();
      const matchNodes = nds.filter(n => n.data?.label?.toLowerCase().includes(query) || n.data?.type?.toLowerCase().includes(query)).map(n => n.id);
      
      const highlightedEdges = new Set();
      const visitedNodes = new Set(matchNodes);
      let queue = [...matchNodes];

      while(queue.length > 0) {
        const curr = queue.shift();
        eds.forEach(e => {
          if (e.source === curr && !visitedNodes.has(e.target)) {
            highlightedEdges.add(e.id); visitedNodes.add(e.target); queue.push(e.target);
          }
          if (e.target === curr && !visitedNodes.has(e.source)) {
            highlightedEdges.add(e.id); visitedNodes.add(e.source); queue.push(e.source);
          }
        });
      }

      return eds.map(e => ({
        ...e,
        style: { opacity: highlightedEdges.has(e.id) ? 1 : 0.05, transition: 'all 0.3s ease' },
        animated: highlightedEdges.has(e.id)
      }));
    });
  }, [searchQuery, rfInstance, setNodes, setEdges]);

  const onConnect = useCallback((params) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  // SINGLE CLICK: Select node only. Does NOT force open the sidebar.
  const onNodeClick = useCallback((event, node) => {
    setContextMenu(null);
    setSelectedNode(node);
  }, []);

  // CLEAR SELECTION: Clicking empty canvas clears selected node and sidebar
  const onPaneClick = useCallback(() => {
    setContextMenu(null);
    setSelectedNode(null);
    setIsSidebarOpen(false);
  }, []);

  const getDescendants = (nodeId, allEdges) => {
    const descendants = [];
    const queue = [nodeId];
    while (queue.length > 0) {
      const curr = queue.shift();
      const children = allEdges.filter(e => e.source === curr).map(e => e.target);
      descendants.push(...children);
      queue.push(...children);
    }
    return descendants;
  };

  // DOUBLE CLICK: Smart Expand/Collapse
  const onNodeDoubleClick = useCallback((event, node) => {
    const currentEdges = rfInstance.getEdges();
    const currentNodes = rfInstance.getNodes();
    
    const childEdges = currentEdges.filter(e => e.source === node.id);
    if (childEdges.length > 0) {
      const descendants = getDescendants(node.id, currentEdges);
      const remainingNodes = currentNodes.filter(n => !descendants.includes(n.id));
      const remainingEdges = currentEdges.filter(e => !descendants.includes(e.target) && !descendants.includes(e.source));
      
      const { layoutedNodes, layoutedEdges } = getLayoutedElements(remainingNodes, remainingEdges);
      setNodes(layoutedNodes);
      setEdges(layoutedEdges);
      setTimeout(() => rfInstance?.fitView({ padding: 0.2, duration: 800 }), 50);
      return;
    }

    if (node.type === 'cable') {
      apiClient.get(`/topology/expand/${node.id}`)
        .then((response) => {
          const existingNodeIds = new Set(currentNodes.map(n => n.id));
          const newNodes = response.data.nodes.filter(n => !existingNodeIds.has(n.id));
          
          const existingEdgeIds = new Set(currentEdges.map(e => e.id));
          const newEdges = response.data.edges.filter(e => !existingEdgeIds.has(e.id));

          const combinedNodes = [...currentNodes, ...newNodes];
          const combinedEdges = [...currentEdges, ...newEdges];

          const { layoutedNodes, layoutedEdges } = getLayoutedElements(combinedNodes, combinedEdges);
          setNodes(layoutedNodes);
          setEdges(layoutedEdges);

          setTimeout(() => {
            if (rfInstance) rfInstance.fitView({ padding: 0.2, duration: 800 });
          }, 100);
        })
        .catch(console.error);
    }
  }, [rfInstance, setNodes, setEdges]);

  // Context Menu Logic
  const onNodeContextMenu = useCallback((event, node) => {
    event.preventDefault(); 
    setSelectedNode(node);
    setContextMenu({
      id: node.id,
      top: event.clientY,
      left: event.clientX,
      node: node
    });
  }, []);

  return (
    <div className="h-full w-full flex flex-col space-y-4 relative overflow-hidden">
      
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-semibold text-white">Network Topology Viewer</h2>
        <div className="flex items-center space-x-4 z-10">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
            <input
              type="text"
              placeholder="Find nodes, customers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-4 py-1.5 w-64 bg-charcoal-800 border border-charcoal-700 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400"
            />
          </div>
        </div>
      </div>

      <div className="flex-1 bg-charcoal-900 border border-charcoal-700 rounded-xl overflow-hidden relative shadow-inner">
        <ReactFlow
          onInit={setRfInstance}
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick} 
          onPaneClick={onPaneClick} // Clears selection when clicking empty space
          onNodeDoubleClick={onNodeDoubleClick} 
          onNodeContextMenu={onNodeContextMenu}
          fitView
          fitViewOptions={{ padding: 0.2 }}
        >
          <Background color="#334155" gap={16} size={1} />
          <Controls className="bg-charcoal-800 fill-white border-charcoal-700" />
          <MiniMap maskColor="rgba(15, 23, 42, 0.7)" className="bg-charcoal-800 border-charcoal-700" />
        </ReactFlow>

        {/* FLOATING ACTION PILL: Appears when a node is selected but sidebar is closed */}
        {selectedNode && !isSidebarOpen && (
          <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 bg-charcoal-800 border border-charcoal-700 shadow-cyan-glow rounded-full px-6 py-3 flex items-center space-x-4 z-40 animate-slide-in-right">
            <span className="text-gray-300 text-sm">
              Selected: <strong className="text-white ml-1">{selectedNode.data?.label}</strong>
            </span>
            <div className="h-4 w-px bg-charcoal-700"></div>
            <button 
              onClick={() => setIsSidebarOpen(true)}
              className="flex items-center text-cyan-400 text-sm font-semibold hover:text-cyan-300 transition-colors"
            >
              <Eye size={16} className="mr-2" />
              View Node Details
            </button>
          </div>
        )}

        {/* Right-Click Context Menu */}
        {contextMenu && (
          <div 
            className="absolute z-50 bg-charcoal-800 border border-charcoal-700 shadow-cyan-glow rounded-lg py-2 w-56 text-sm"
            style={{ top: contextMenu.top, left: contextMenu.left }}
          >
            <div className="px-4 py-1 text-xs text-gray-400 border-b border-charcoal-700 mb-1 truncate">
              {contextMenu.node.data?.label}
            </div>
            {/* Added View Details to Context Menu */}
            <button 
              onClick={() => { setIsSidebarOpen(true); setContextMenu(null); }}
              className="w-full text-left px-4 py-2 hover:bg-charcoal-700 text-white transition-colors"
            >
              👁️ View Node Details
            </button>
            <button className="w-full text-left px-4 py-2 hover:bg-charcoal-700 text-cyan-400 transition-colors">⚡ Run Fiber Trace</button>
            <button className="w-full text-left px-4 py-2 hover:bg-charcoal-700 text-white transition-colors">🎫 Create Ticket</button>
            <button className="w-full text-left px-4 py-2 hover:bg-charcoal-700 text-red-400 transition-colors">🔴 Mark as Offline</button>
          </div>
        )}

        {/* Slide-Out Sidebar */}
        <div className={`absolute top-0 right-0 w-80 h-full bg-charcoal-800 border-l border-charcoal-700 shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-in-out ${isSidebarOpen ? 'translate-x-0' : 'translate-x-full'}`}>
          {selectedNode && (
            <>
              <div className="p-4 border-b border-charcoal-700 flex justify-between items-center bg-[#0f172a]">
                <div className="flex items-center space-x-2">
                  <Info className="text-cyan-400" size={20} />
                  <h3 className="text-lg font-bold text-white tracking-wide">
                    {selectedNode.data?.label || 'Node Details'}
                  </h3>
                </div>
                <button onClick={() => setIsSidebarOpen(false)} className="text-gray-400 hover:text-white transition-colors">
                  <X size={24} />
                </button>
              </div>

              <div className="p-4 flex-1 overflow-y-auto text-sm space-y-4">
                <div className="bg-charcoal-900 p-3 rounded-lg border border-charcoal-700 shadow-sm">
                  <div className="flex items-center text-gray-400 mb-1">
                    <Hash size={14} className="mr-1" />
                    <span className="text-xs uppercase tracking-wider">Node Type</span>
                  </div>
                  <div className="font-semibold text-white capitalize">{selectedNode.data?.type || selectedNode.type}</div>
                </div>

                {selectedNode.data?.badge && (
                  <div className="bg-charcoal-900 p-3 rounded-lg border border-charcoal-700 shadow-sm">
                    <div className="flex items-center text-gray-400 mb-1">
                      <MapPin size={14} className="mr-1" />
                      <span className="text-xs uppercase tracking-wider">Allocation / Capacity</span>
                    </div>
                    <div className="font-semibold text-cyan-400">{selectedNode.data.badge}</div>
                  </div>
                )}

                <div className="bg-charcoal-900 p-3 rounded-lg border border-charcoal-700 shadow-sm">
                  <div className="flex items-center text-gray-400 mb-1">
                    <ActivityIcon size={14} className="mr-1" />
                    <span className="text-xs uppercase tracking-wider">Current Status</span>
                  </div>
                  <div className="font-semibold text-green-400 flex items-center">
                    <span className="w-2 h-2 rounded-full bg-green-500 mr-2 animate-pulse"></span> 
                    Online & Active
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default TopologyMap;