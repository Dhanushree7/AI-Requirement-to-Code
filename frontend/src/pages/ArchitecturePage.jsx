import React, { useState, useEffect } from 'react';
import { 
  Layers, 
  Sparkles, 
  RefreshCw, 
  AlertCircle, 
  CheckCircle2, 
  Cpu, 
  Server, 
  Database, 
  Globe, 
  Loader2,
  History 
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { projectApi } from '../api';
import MermaidViewer from '../components/MermaidViewer';
import VersionHistoryDrawer from '../components/VersionHistoryDrawer';
import EmptyArtifactState from '../components/EmptyArtifactState';
import MarkdownViewer from '../components/MarkdownViewer';

export default function ArchitecturePage() {
  const { activeProjectId } = useProject();
  const [artifact, setArtifact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const loadArtifact = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      const data = await projectApi.getArtifact(activeProjectId, 'architecture');
      setArtifact(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadArtifact();
  }, [activeProjectId]);

  const handleRegenerate = async () => {
    if (!activeProjectId || regenerating) return;
    setRegenerating(true);
    try {
      const updated = await projectApi.regenerateArtifact(activeProjectId, 'architecture', {});
      setArtifact(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setRegenerating(false);
    }
  };

  const handleRestore = async (versionNumber) => {
    if (!window.confirm(`Restore version ${versionNumber}?`)) return;
    try {
      const restored = await projectApi.restoreVersion(activeProjectId, 'architecture', versionNumber);
      setArtifact(restored);
      setShowHistory(false);
    } catch (err) {
      console.error(err);
    }
  };

  const extractLayers = (data) => {
    if (!data) return [];
    if (Array.isArray(data.layers) && data.layers.length > 0) return data.layers;
    if (Array.isArray(data.components)) return data.components;
    if (typeof data.layers === 'object' && data.layers !== null) {
      return Object.entries(data.layers).map(([k, v]) => ({
        name: k,
        tech: v?.tech || 'Python / FastAPI',
        responsibility: v?.responsibility || String(v || '')
      }));
    }
    return [];
  };

  const content = artifact?.content || {};
  const layers = extractLayers(content);
  const mermaidDiagram = content.mermaid_diagram || content.mermaid || '';
  const justification = content.justification || '';
  const pattern = content.pattern || 'Layered Architecture';

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-blue-500/10 text-blue-400 border border-blue-500/20">
              System Architecture
            </span>
            <span className="text-xs font-mono text-slate-400">
              {pattern}
            </span>
          </div>
          <h1 className="text-3xl font-serif font-bold text-white tracking-tight mt-1">
            System Architecture
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Suggested layered design and component responsibilities - review before adopting.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5"
            title="Version history"
          >
            <History className="w-3.5 h-3.5 text-slate-400" />
            <span>History ({artifact?.versions?.length || 1})</span>
          </button>
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-2 border border-slate-700 disabled:opacity-50"
          >
            {regenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin text-orange-400" /> : <RefreshCw className="w-3.5 h-3.5 text-orange-400" />}
            <span>Regenerate Architecture</span>
          </button>
        </div>
      </div>

      {/* Version History Drawer */}
      <VersionHistoryDrawer
        isOpen={showHistory}
        onClose={() => setShowHistory(false)}
        versions={artifact?.versions}
        currentVersion={artifact?.current_version}
        onRestore={handleRestore}
        artifactName="Architecture"
      />

      {loading ? (
        <div className="p-16 text-center text-slate-400 text-sm flex items-center justify-center gap-2 bg-[#131B2E] border border-slate-800 rounded-2xl">
          <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
          <span>Generating architecture diagram...</span>
        </div>
      ) : (!artifact || (layers.length === 0 && !mermaidDiagram)) ? (
        <EmptyArtifactState
          title="Architecture Not Generated Yet"
          description="Synthesize an architectural component topology, layered system structure, and Mermaid interactive component diagrams based on project requirements."
          icon={Layers}
          onGenerate={handleRegenerate}
          isGenerating={regenerating}
          generateLabel="Generate Architecture"
        />
      ) : (
        <>
          {/* Mermaid Diagram Card */}
          <div className="bg-[#131B2E] border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="text-xs font-mono uppercase text-slate-400 tracking-wider font-semibold">
                Interactive Layered Component Topology
              </div>
              <span className="text-[11px] font-mono text-teal-400 bg-teal-500/10 px-2 py-0.5 rounded border border-teal-500/20">
                Rendered with Mermaid
              </span>
            </div>

            <div className="min-h-[300px] flex items-center justify-center bg-[#0D1424] rounded-xl border border-slate-800/80">
              {mermaidDiagram ? (
                <MermaidViewer chart={mermaidDiagram} id="architecture-chart" />
              ) : (
                <div className="text-xs text-slate-500">No diagram available</div>
              )}
            </div>
          </div>

          {/* Layer Breakdown Grid */}
          {layers.length > 0 && (
            <div className="space-y-3">
              <div className="text-xs font-mono uppercase text-slate-400 tracking-wider font-semibold">
                Layer Responsibilities & Tech Stack ({layers.length})
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {layers.map((layer, idx) => (
                  <div key={idx} className="bg-[#131B2E] border border-slate-800 rounded-2xl p-5 shadow-lg space-y-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center justify-center shrink-0 font-mono text-xs font-bold">
                        0{idx + 1}
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-white">{layer.name}</h4>
                        <div className="text-[11px] font-mono text-orange-400">{layer.tech}</div>
                      </div>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {layer.responsibility}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Justification & Architectural Rationale Callout */}
          {justification && (
            <div className="bg-[#131B2E] border border-slate-800 rounded-2xl p-6 shadow-xl space-y-2">
              <h4 className="text-xs font-mono uppercase text-slate-400 tracking-wider font-semibold flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-teal-400" /> Architectural Justification
              </h4>
              <MarkdownViewer content={justification} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
