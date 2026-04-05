import React, { useCallback, useMemo, useState, useEffect } from 'react';
import ReactFlow, { 
  MiniMap, Controls, Background, useNodesState, useEdgesState, addEdge
} from 'reactflow';
import dagre from 'dagre';
import 'reactflow/dist/style.css';
import apiClient from '../api/client'; 

import { CoreNode, CableNode, SplitterNode, CustomerNode } from '../components/TopologyNodes';
import { Activity, X, Info, Activity as ActivityIcon, MapPin, Hash, Search, Eye, Navigation, Wrench } from 'lucide-react';

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
      position: { x: nodeWithPosition.x - 140, y: nodeWithPosition.y - 50 },
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

  // --- Master State Variables ---
  const [originalData, setOriginalData] = useState({ nodes: [], edges: [] });
  const [collapsedNodes, setCollapsedNodes] = useState(new Set());
  
  // --- React Flow State ---
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  
  // --- UI State ---
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [rfInstance, setRfInstance] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [contextMenu, setContextMenu] = useState(null);

  // --- Helper: Format Edges ---
  const formatEdges = (edgesToFormat) => edgesToFormat.map(e => ({
    ...e, type: 'smoothstep', style: { strokeWidth: 2, stroke: '#64748b' }
  }));

  // --- Fetch Base Topology ---
  useEffect(() => {
    apiClient.get('/topology/')
      .then((response) => {
        const styledEdges = formatEdges(response.data.edges);
        setOriginalData({ nodes: response.data.nodes, edges: styledEdges });

        const { layoutedNodes, layoutedEdges } = getLayoutedElements(response.data.nodes, styledEdges);
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

  const onConnect = useCallback((params) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  // --- Traversal Helpers ---
  const getDescendants = useCallback((nodeId, allEdges) => {
    const descendants = [];
    const queue = [nodeId];
    while (queue.length > 0) {
      const curr = queue.shift();
      const children = allEdges.filter(e => e.source === curr).map(e => e.target);
      descendants.push(...children);
      queue.push(...children);
    }
    return descendants;
  }, []);

  const getConnectedGraph = useCallback((targetNodeId, allEdges) => {
    const connectedNodes = new Set([targetNodeId]);
    const connectedEdges = new Set();
    // Upstream
    let queue = [targetNodeId];
    while (queue.length > 0) {
      const current = queue.shift();
      allEdges.forEach(edge => {
        if (edge.target === current) {
          connectedEdges.add(edge.id);
          if (!connectedNodes.has(edge.source)) { connectedNodes.add(edge.source); queue.push(edge.source); }
        }
      });
    }
    // Downstream
    queue = [targetNodeId];
    while (queue.length > 0) {
      const current = queue.shift();
      allEdges.forEach(edge => {
        if (edge.source === current) {
          connectedEdges.add(edge.id);
          if (!connectedNodes.has(edge.target)) { connectedNodes.add(edge.target); queue.push(edge.target); }
        }
      });
    }
    return { connectedNodes, connectedEdges };
  }, []);

  // --- Render Visible Layout ---
  const updateVisibleLayout = useCallback((origNodes, origEdges, collapsedSet) => {
    const hiddenNodeIds = new Set();
    collapsedSet.forEach(collapsedId => {
      const descendants = getDescendants(collapsedId, origEdges);
      descendants.forEach(d => hiddenNodeIds.add(d));
    });

    const activeNodes = origNodes.filter(n => !hiddenNodeIds.has(n.id));
    const activeEdges = origEdges.filter(e => !hiddenNodeIds.has(e.target) && !hiddenNodeIds.has(e.source));

    const { layoutedNodes, layoutedEdges } = getLayoutedElements(activeNodes, activeEdges);
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [getDescendants, setNodes, setEdges]);

  // --- Search & Camera Controls ---
  const executeSearch = (term) => {
    if (!term || !term.trim()) { clearSearch(); return; }
    if (!rfInstance) return;

    const targetNode = nodes.find(n => 
      n.data?.label?.toLowerCase().includes(term.toLowerCase()) || n.id.toLowerCase().includes(term.toLowerCase())
    );

    if (targetNode) {
      const { connectedNodes, connectedEdges } = getConnectedGraph(targetNode.id, edges);
      setNodes(nds => nds.map(n => ({ ...n, style: { ...n.style, opacity: connectedNodes.has(n.id) ? 1 : 0.15, transition: 'opacity 0.4s ease' }})));
      setEdges(eds => eds.map(e => ({ ...e, style: { ...e.style, opacity: connectedEdges.has(e.id) ? 1 : 0.05, transition: 'opacity 0.4s ease' }, animated: connectedEdges.has(e.id)})));
      rfInstance.fitBounds({ x: targetNode.position.x - 200, y: targetNode.position.y - 200, width: 400, height: 400 }, { duration: 1000 });
    }
  };

  const clearSearch = () => {
    setSearchQuery("");
    setCollapsedNodes(new Set()); // Auto-expand everything on clear
    updateVisibleLayout(originalData.nodes, originalData.edges, new Set());
    setTimeout(() => recenterMap(), 50);
  };

  const recenterMap = () => {
    if (rfInstance) rfInstance.fitView({ padding: 0.2, duration: 800 });
  };

  // --- Node Interactions ---
  const onNodeClick = useCallback((event, node) => { setContextMenu(null); setSelectedNode(node); }, []);
  const onPaneClick = useCallback(() => { setContextMenu(null); setSelectedNode(null); setIsSidebarOpen(false); }, []);
  const onNodeContextMenu = useCallback((event, node) => {
    event.preventDefault(); setSelectedNode(node); setContextMenu({ id: node.id, top: event.clientY, left: event.clientX, node: node });
  }, []);

  // --- Flawless Expand / Collapse Logic ---
  const onNodeDoubleClick = useCallback((event, node) => {
    const childEdges = originalData.edges.filter(e => e.source === node.id);
    
    // 1. If we already fetched the children previously, just toggle visibility
    if (childEdges.length > 0) {
      setCollapsedNodes(prev => {
        const newCollapsed = new Set(prev);
        if (newCollapsed.has(node.id)) newCollapsed.delete(node.id); // Expand
        else newCollapsed.add(node.id); // Collapse
        
        updateVisibleLayout(originalData.nodes, originalData.edges, newCollapsed);
        setTimeout(() => rfInstance?.fitView({ padding: 0.2, duration: 800 }), 50);
        return newCollapsed;
      });
      return;
    }

    // 2. If no children exist in memory and it's a cable, fetch from API
    if (node.type === 'cable') {
      apiClient.get(`/topology/expand/${node.id}`)
        .then((response) => {
          const existingNodeIds = new Set(originalData.nodes.map(n => n.id));
          const existingEdgeIds = new Set(originalData.edges.map(e => e.id));
          
          const newNodes = response.data.nodes.filter(n => !existingNodeIds.has(n.id));
          const newEdges = formatEdges(response.data.edges.filter(e => !existingEdgeIds.has(e.id)));

          const combinedNodes = [...originalData.nodes, ...newNodes];
          const combinedEdges = [...originalData.edges, ...newEdges];

          setOriginalData({ nodes: combinedNodes, edges: combinedEdges });
          updateVisibleLayout(combinedNodes, combinedEdges, collapsedNodes);

          setTimeout(() => { if (rfInstance) rfInstance.fitView({ padding: 0.2, duration: 800 }); }, 100);
        })
        .catch(console.error);
    }
  }, [originalData, collapsedNodes, updateVisibleLayout, rfInstance]);


  if (loading) return <div className="h-full w-full flex items-center justify-center bg-charcoal-900"><Activity className="animate-spin text-cyan-500 mb-4" size={32} /></div>;

  return (
    <div className="h-full w-full flex flex-col relative overflow-hidden bg-charcoal-950 rounded-xl border border-charcoal-700 shadow-inner">
      
      {/* Search & Control Overlay */}
      <div className="absolute top-4 left-4 z-10 flex items-center space-x-3 bg-charcoal-900/80 p-2 rounded-lg backdrop-blur-sm border border-charcoal-700 shadow-xl">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
          <input type="text" placeholder="Search nodes, IDs..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && executeSearch(searchQuery)} className="pl-9 pr-4 py-1.5 w-64 bg-charcoal-800 border border-charcoal-600 rounded-md text-sm text-white focus:outline-none focus:border-cyan-400" />
        </div>
        <button onClick={() => executeSearch(searchQuery)} className="bg-cyan-600 hover:bg-cyan-500 text-white px-3 py-1.5 rounded-md text-sm transition-colors">Highlight</button>
        <div className="h-5 w-px bg-charcoal-600 mx-1"></div>
        <button onClick={clearSearch} className="bg-charcoal-800 hover:bg-charcoal-700 text-gray-300 px-3 py-1.5 rounded-md border border-charcoal-600 text-sm transition-colors">Clear Map</button>
        <button onClick={recenterMap} className="bg-charcoal-800 hover:bg-charcoal-700 text-cyan-400 px-3 py-1.5 rounded-md border border-charcoal-600 flex items-center text-sm transition-colors"><MapPin size={14} className="mr-2" /> Recenter</button>
      </div>

      <ReactFlow
        onInit={setRfInstance} nodes={nodes} edges={edges} nodeTypes={nodeTypes}
        onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
        onNodeClick={onNodeClick} onPaneClick={onPaneClick} onNodeDoubleClick={onNodeDoubleClick} 
        onNodeContextMenu={onNodeContextMenu} fitView
      >
        <Background color="#334155" gap={16} size={1} />
        <Controls className="bg-charcoal-800 fill-white border-charcoal-700" />
        <MiniMap maskColor="rgba(15, 23, 42, 0.7)" className="bg-charcoal-800 border-charcoal-700" />
      </ReactFlow>

      {/* Context Menu */}
      {contextMenu && (
        <div className="absolute z-50 bg-charcoal-800 border border-charcoal-600 shadow-2xl rounded-lg py-2 w-56 text-sm" style={{ top: contextMenu.top, left: contextMenu.left }}>
          <div className="px-4 py-1 text-xs text-gray-400 font-semibold uppercase tracking-wider border-b border-charcoal-700 mb-1">{contextMenu.node.data?.label}</div>
          <button onClick={() => { setIsSidebarOpen(true); setContextMenu(null); }} className="w-full text-left px-4 py-2 hover:bg-charcoal-700 text-gray-200 flex items-center transition-colors"><Eye size={16} className="mr-3 text-cyan-400" /> View Node Details</button>
          <button onClick={() => { executeSearch(contextMenu.node.data.label); setContextMenu(null); }} className="w-full text-left px-4 py-2 hover:bg-charcoal-700 text-gray-200 flex items-center transition-colors"><Navigation size={16} className="mr-3 text-purple-400" /> Run Fiber Trace</button>
          <button onClick={() => { alert(`Opening Incident Ticket for: ${contextMenu.node.data.label}`); setContextMenu(null); }} className="w-full text-left px-4 py-2 hover:bg-charcoal-700 text-gray-200 flex items-center transition-colors"><Wrench size={16} className="mr-3 text-orange-400" /> Create Ticket</button>
        </div>
      )}

      {/* Floating Action Pill */}
      {selectedNode && !isSidebarOpen && (
        <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 bg-charcoal-800 border border-cyan-500/50 shadow-2xl rounded-full px-6 py-3 flex items-center gap-4 z-40 animate-fade-in-up">
          <span className="text-gray-400 text-sm">Selected: <strong className="text-white ml-1">{selectedNode.data?.label}</strong></span>
          <div className="h-5 w-px bg-charcoal-600"></div>
          <button onClick={() => setIsSidebarOpen(true)} className="flex items-center text-cyan-400 text-sm font-semibold hover:text-cyan-300 transition-colors"><Eye size={16} className="mr-2" /> View Details</button>
        </div>
      )}

      {/* Slide-Out Sidebar */}
      <div className={`absolute top-0 right-0 w-80 h-full bg-charcoal-900 border-l border-charcoal-700 shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-in-out ${isSidebarOpen ? 'translate-x-0' : 'translate-x-full'}`}>
        {selectedNode && (
          <>
            <div className="p-4 border-b border-charcoal-700 flex justify-between items-center bg-charcoal-950">
              <div className="flex items-center space-x-2"><Info className="text-cyan-400" size={20} /><h3 className="text-lg font-bold text-white tracking-wide truncate">{selectedNode.data?.label}</h3></div>
              <button onClick={() => setIsSidebarOpen(false)} className="text-gray-400 hover:text-white transition-colors"><X size={20} /></button>
            </div>
            <div className="p-4 flex-1 overflow-y-auto text-sm space-y-4">
              <div className="bg-charcoal-800 p-3 rounded-lg border border-charcoal-700"><div className="flex items-center text-gray-400 mb-1"><Hash size={14} className="mr-2" /><span className="text-xs uppercase tracking-wider">Type</span></div><div className="font-semibold text-white capitalize">{selectedNode.data?.type || selectedNode.type}</div></div>
              {selectedNode.data?.badge && (<div className="bg-charcoal-800 p-3 rounded-lg border border-charcoal-700"><div className="flex items-center text-gray-400 mb-1"><MapPin size={14} className="mr-2" /><span className="text-xs uppercase tracking-wider">Capacity</span></div><div className="font-semibold text-cyan-400">{selectedNode.data.badge}</div></div>)}
              <div className="bg-charcoal-800 p-3 rounded-lg border border-charcoal-700"><div className="flex items-center text-gray-400 mb-2"><ActivityIcon size={14} className="mr-2" /><span className="text-xs uppercase tracking-wider">Status</span></div><div className="font-semibold text-green-400 flex items-center"><span className="w-2.5 h-2.5 rounded-full bg-green-500 mr-2 animate-pulse"></span> Online & Active</div></div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default TopologyMap;