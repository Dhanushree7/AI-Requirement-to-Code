import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  ReactFlow, 
  Controls, 
  Background, 
  MiniMap, 
  useNodesState, 
  useEdgesState,
  MarkerType
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { 
  Network, 
  Share2, 
  Filter, 
  Table, 
  AlertTriangle, 
  ArrowRight, 
  CheckCircle2, 
  Info,
  Loader2 
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { projectApi } from '../api';

const nodeTypeColors = {
  Requirement: '#F97316',      // orange
  Actor: '#EC4899',            // pink
  Module: '#8B5CF6',           // purple
  API: '#06B6D4',              // cyan
  'Database Entity': '#10B981',// emerald
  'Test Case': '#F59E0B',      // amber
};

export default function KnowledgeGraphPage() {
  const { activeProjectId } = useProject();
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('graph'); // 'graph' | 'matrix' | 'impact'
  
  // Graph state
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [filterType, setFilterType] = useState('ALL');

  // Impact Analysis state
  const [impactResult, setImpactResult] = useState(null);
  const [analyzingImpact, setAnalyzingImpact] = useState(false);
  const [selectedImpactReq, setSelectedImpactReq] = useState('');

  const loadGraph = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      const data = await projectApi.getGraph(activeProjectId);
      setGraphData(data);

      // Transform nodes into React Flow format with a circular/layered layout
      const rawNodes = data.nodes || [];
      const rawEdges = data.edges || [];

      const typeAngles = {
        Actor: { angleStart: 0, r: 180 },
        Requirement: { angleStart: 60, r: 240 },
        Module: { angleStart: 120, r: 200 },
        API: { angleStart: 180, r: 260 },
        'Database Entity': { angleStart: 240, r: 220 },
        'Test Case': { angleStart: 300, r: 260 },
      };

      const flowNodes = rawNodes.map((n, i) => {
        const typeInfo = typeAngles[n.type] || { angleStart: 0, r: 200 };
        const angle = (i * (360 / Math.max(rawNodes.length, 1))) * (Math.PI / 180);
        const x = 400 + Math.cos(angle) * (typeInfo.r + (i % 3) * 60);
        const y = 300 + Math.sin(angle) * (typeInfo.r + (i % 3) * 50);

        const nodeColor = nodeTypeColors[n.type] || '#64748B';

        return {
          id: n.id,
          position: { x, y },
          className: 'react-flow-node',
          data: { 
            label: (
              <div className="text-left font-sans">
                <div className="text-[10px] font-mono uppercase font-bold" style={{ color: nodeColor }}>
                  {n.type}
                </div>
                <div className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate max-w-[150px]">
                  {n.id}: {n.label}
                </div>
              </div>
            ),
            rawNode: n
          },
          style: {
            border: `1.5px solid ${nodeColor}`,
            borderRadius: '12px',
            padding: '8px 12px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
            cursor: 'pointer'
          }
        };
      });

      const flowEdges = rawEdges.map((e, i) => ({
        id: e.id || `edge-${i}`,
        source: e.source,
        target: e.target,
        label: e.label,
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#94A3B8', strokeWidth: 1.5 },
        labelStyle: { fill: '#64748B', fontSize: 10, fontFamily: 'monospace' },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#94A3B8',
        },
      }));

      setNodes(flowNodes);
      setEdges(flowEdges);

      // Select first requirement for impact test
      const firstReq = rawNodes.find(n => n.type === 'Requirement');
      if (firstReq) setSelectedImpactReq(firstReq.id);

    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGraph();
  }, [activeProjectId]);

  const onNodeClick = useCallback((event, node) => {
    setSelectedNode(node.data.rawNode);
  }, []);

  const handleRunImpact = async () => {
    if (!selectedImpactReq || !activeProjectId) return;
    setAnalyzingImpact(true);
    try {
      const res = await projectApi.getImpactAnalysis(activeProjectId, selectedImpactReq);
      setImpactResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setAnalyzingImpact(false);
    }
  };

  const matrix = graphData?.matrix || [];
  const stats = graphData?.stats || {};

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-purple-500/10 text-purple-400 border border-purple-500/20">
              System Knowledge Graph &bull; Traceability
            </span>
            <span className="text-xs font-mono text-slate-400">
              {stats.total_nodes || 0} Nodes &bull; {stats.total_edges || 0} Edges
            </span>
          </div>
          <h1 className="text-3xl font-serif font-bold text-white tracking-tight mt-1">
            Knowledge Graph & Traceability
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Traceability links from Requirements &rarr; Modules &rarr; APIs &rarr; Database Entities &rarr; Test Cases.
          </p>
        </div>

        {/* View Tabs */}
        <div className="flex items-center gap-2 bg-[#131B2E] p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('graph')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors ${
              activeTab === 'graph' ? 'bg-orange-500 text-white font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            <span>Interactive Graph</span>
          </button>
          <button
            onClick={() => setActiveTab('matrix')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors ${
              activeTab === 'matrix' ? 'bg-orange-500 text-white font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Table className="w-3.5 h-3.5" />
            <span>Traceability Matrix</span>
          </button>
          <button
            onClick={() => {
              setActiveTab('impact');
              if (!impactResult) handleRunImpact();
            }}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors ${
              activeTab === 'impact' ? 'bg-orange-500 text-white font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Impact Analysis</span>
          </button>
        </div>
      </div>

      {loading ? (
        <div className="p-16 text-center text-slate-400 text-sm flex items-center justify-center gap-2 bg-[#131B2E] border border-slate-800 rounded-2xl">
          <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
          <span>Building knowledge graph...</span>
        </div>
      ) : (
        <>
          {/* TAB 1: INTERACTIVE REACT FLOW GRAPH */}
          {activeTab === 'graph' && (
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
              {/* Canvas Area */}
              <div className="lg:col-span-3 h-[580px] bg-[#0E131F] border border-slate-800 rounded-2xl overflow-hidden relative shadow-2xl">
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onNodeClick={onNodeClick}
                  fitView
                >
                  <Background color="#1E293B" gap={20} size={1} />
                  <Controls className="!bg-[#162035] !border-slate-700 !text-slate-200" />
                  <MiniMap 
                    nodeColor={(n) => {
                      const type = n.data?.rawNode?.type;
                      return nodeTypeColors[type] || '#64748B';
                    }}
                    className="!bg-[#0B0F17] !border-slate-800 !rounded-xl"
                  />
                </ReactFlow>

                {/* Node Type Legend */}
                <div className="absolute top-4 left-4 bg-[#131B2E]/90 backdrop-blur-md p-3 rounded-xl border border-slate-800 flex flex-wrap gap-3 text-[11px] font-mono select-none">
                  {Object.entries(nodeTypeColors).map(([type, color]) => (
                    <div key={type} className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                      <span className="text-slate-300">{type}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Node Inspector Panel */}
              <div className="lg:col-span-1 bg-[#131B2E] border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col justify-between">
                <div>
                  <div className="text-xs font-mono uppercase text-slate-400 tracking-wider font-semibold border-b border-slate-800 pb-3 flex items-center gap-2">
                    <Info className="w-4 h-4 text-orange-400" />
                    <span>Node Inspector</span>
                  </div>

                  {selectedNode ? (
                    <div className="mt-4 space-y-3 animate-in fade-in duration-150">
                      <div>
                        <span 
                          className="px-2 py-0.5 rounded text-[10px] font-mono uppercase font-bold"
                          style={{ 
                            backgroundColor: `${nodeTypeColors[selectedNode.type]}20`,
                            color: nodeTypeColors[selectedNode.type] 
                          }}
                        >
                          {selectedNode.type}
                        </span>
                        <h3 className="text-sm font-bold text-white mt-1.5">
                          {selectedNode.label}
                        </h3>
                        <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                          Node ID: {selectedNode.id}
                        </div>
                      </div>

                      {selectedNode.data?.description && (
                        <div className="p-3 bg-[#0E1424] rounded-xl border border-slate-800 text-xs text-slate-300 leading-relaxed">
                          {selectedNode.data.description}
                        </div>
                      )}

                      <div className="pt-2">
                        <button
                          onClick={() => {
                            setSelectedImpactReq(selectedNode.id);
                            setActiveTab('impact');
                            handleRunImpact();
                          }}
                          className="w-full py-2 rounded-xl bg-orange-500/20 hover:bg-orange-500/30 text-orange-300 text-xs font-semibold border border-orange-500/30 flex items-center justify-center gap-1.5"
                        >
                          <AlertTriangle className="w-3.5 h-3.5" /> Analyze Impact Radius
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-8 text-center text-xs text-slate-500 leading-relaxed">
                      Click any node on the graph canvas to inspect its relationships and metadata.
                    </div>
                  )}
                </div>

                <div className="pt-4 border-t border-slate-800 text-[11px] font-mono text-slate-500 text-center">
                  Graph persistence: NetworkX JSON
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: TRACEABILITY MATRIX */}
          {activeTab === 'matrix' && (
            <div className="bg-[#131B2E] border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
              <div className="p-4 bg-[#162035] border-b border-slate-800 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white">Full Traceability Matrix</h3>
                  <p className="text-xs text-slate-400">Verifies coverage from Requirement to Implementation and Test Verification.</p>
                </div>
                <span className="text-xs font-mono text-teal-400 bg-teal-500/10 px-2.5 py-1 rounded-full border border-teal-500/20">
                  {matrix.length} Specifications Covered
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[#0E1424] text-slate-400 text-[10px] uppercase border-b border-slate-800">
                    <tr>
                      <th className="py-3 px-4">Req ID</th>
                      <th className="py-3 px-4 font-sans">Requirement Title</th>
                      <th className="py-3 px-4">Module</th>
                      <th className="py-3 px-4">API Endpoints</th>
                      <th className="py-3 px-4">DB Entities</th>
                      <th className="py-3 px-4">Test Cases</th>
                      <th className="py-3 px-4">Coverage</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-[11px]">
                    {matrix.map((row, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4 text-orange-400 font-bold">{row.requirement_id}</td>
                        <td className="py-3 px-4 font-sans text-slate-200 font-medium">{row.requirement_title}</td>
                        <td className="py-3 px-4 text-purple-400">{row.module}</td>
                        <td className="py-3 px-4 text-cyan-400">
                          {row.apis?.length > 0 ? row.apis.join(', ') : <span className="text-slate-600">-</span>}
                        </td>
                        <td className="py-3 px-4 text-emerald-400">
                          {row.entities?.length > 0 ? row.entities.join(', ') : <span className="text-slate-600">-</span>}
                        </td>
                        <td className="py-3 px-4 text-amber-400">
                          {row.test_cases?.length > 0 ? row.test_cases.join(', ') : <span className="text-slate-600">-</span>}
                        </td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
                            row.coverage_status === 'complete' 
                              ? 'bg-teal-500/15 text-teal-400 border border-teal-500/30' 
                              : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                          }`}>
                            {row.coverage_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: IMPACT ANALYSIS */}
          {activeTab === 'impact' && (
            <div className="bg-[#131B2E] border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                <div>
                  <h3 className="text-base font-serif font-bold text-white">Change Blast-Radius & Impact Analysis</h3>
                  <p className="text-xs text-slate-400 mt-0.5">Select a requirement or entity to assess which APIs, models, and test cases require modifications.</p>
                </div>

                <div className="flex items-center gap-2">
                  <select
                    value={selectedImpactReq}
                    onChange={(e) => setSelectedImpactReq(e.target.value)}
                    className="bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 font-mono"
                  >
                    {(graphData?.nodes || []).map(n => (
                      <option key={n.id} value={n.id}>
                        [{n.id}] {n.label}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={handleRunImpact}
                    disabled={analyzingImpact}
                    className="px-4 py-2 rounded-xl bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold flex items-center gap-1.5"
                  >
                    {analyzingImpact ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                    <span>Assess Impact</span>
                  </button>
                </div>
              </div>

              {impactResult && (
                <div className="space-y-4 animate-in fade-in duration-200">
                  {/* Summary Box */}
                  <div className="p-4 bg-orange-500/10 border border-orange-500/30 rounded-xl text-orange-200 text-xs leading-relaxed flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-orange-400 shrink-0 mt-0.5" />
                    <div>
                      <div className="font-bold text-white uppercase font-mono text-[11px] mb-1">
                        Impact Blast Radius Summary
                      </div>
                      <p>{impactResult.impact_summary}</p>
                    </div>
                  </div>

                  {/* Affected Nodes Breakdown */}
                  <div>
                    <div className="text-xs font-mono uppercase text-slate-400 tracking-wider mb-3 font-semibold">
                      Directly Affected System Artifacts ({impactResult.affected_nodes.length})
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {impactResult.affected_nodes.map(n => {
                        const color = nodeTypeColors[n.type] || '#64748B';
                        return (
                          <div key={n.id} className="p-3.5 bg-[#0E1424] rounded-xl border border-slate-800 space-y-1">
                            <span className="text-[10px] font-mono uppercase font-bold" style={{ color }}>
                              {n.type}
                            </span>
                            <div className="text-xs font-semibold text-white">
                              {n.id}: {n.label}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
