import React, { useState, useEffect } from 'react';
import { 
  Database, 
  Download, 
  Copy, 
  Check, 
  RefreshCw, 
  Key, 
  Link2, 
  Table, 
  FileCode, 
  AlertCircle, 
  Loader2,
  History 
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { projectApi } from '../api';
import MermaidViewer from '../components/MermaidViewer';
import VersionHistoryDrawer from '../components/VersionHistoryDrawer';
import EmptyArtifactState from '../components/EmptyArtifactState';

export default function DatabaseSchemaPage() {
  const { activeProjectId } = useProject();
  const [artifact, setArtifact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('tables'); // 'tables' | 'er' | 'ddl'
  const [copied, setCopied] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const loadArtifact = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      const data = await projectApi.getArtifact(activeProjectId, 'schema');
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
      const updated = await projectApi.regenerateArtifact(activeProjectId, 'schema', {});
      setArtifact(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setRegenerating(false);
    }
  };

  const extractTables = (data) => {
    if (!data) return [];
    if (Array.isArray(data.tables) && data.tables.length > 0) return data.tables;
    if (Array.isArray(data.entities) && data.entities.length > 0) {
      return data.entities.map(e => ({
        name: e.name || e.entity_name || 'Unnamed',
        description: e.description || '',
        columns: (e.attributes || e.columns || []).map(a => ({
          name: a.name || a.attribute_name || 'col',
          type: a.type || a.data_type || 'VARCHAR(255)',
          pk: !!(a.pk || a.is_primary_key || a.primary_key),
          fk: a.fk || a.foreign_key || null,
          nullable: a.nullable !== undefined ? a.nullable : !(a.pk || a.is_primary_key),
          description: a.description || ''
        }))
      }));
    }
    if (typeof data.tables === 'object' && data.tables !== null && !Array.isArray(data.tables)) {
      return Object.entries(data.tables).map(([k, v]) => ({
        name: k,
        description: v?.description || '',
        columns: Array.isArray(v?.columns) ? v.columns : []
      }));
    }
    return [];
  };

  const content = artifact?.content || {};
  const tables = extractTables(content);
  const mermaidEr = content.mermaid_er || content.mermaid || '';
  const sqlDdl = content.sql_ddl || content.ddl || '';

  const handleCopySql = () => {
    navigator.clipboard.writeText(sqlDdl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadSql = () => {
    const blob = new Blob([sqlDdl], { type: 'text/sql;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `schema_${activeProjectId.slice(0, 8)}.sql`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleRestore = async (versionNumber) => {
    if (!window.confirm(`Restore version ${versionNumber}?`)) return;
    try {
      const restored = await projectApi.restoreVersion(activeProjectId, 'schema', versionNumber);
      setArtifact(restored);
      setShowHistory(false);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-teal-500/10 text-teal-400 border border-teal-500/20">
              Relational Database Schema
            </span>
            <span className="text-xs font-mono text-slate-400">
              {tables.length} Normalized Tables
            </span>
          </div>
          <h1 className="text-3xl font-serif font-bold text-white tracking-tight mt-1">
            Database Schema & ER Model
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Entities, attributes, primary/foreign keys, and relationships derived from requirement text.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5"
            title="Version history"
          >
            <History className="w-3.5 h-3.5 text-slate-400" />
            <span>History ({artifact?.versions?.length || 1})</span>
          </button>
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5 disabled:opacity-50"
          >
            {regenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin text-orange-400" /> : <RefreshCw className="w-3.5 h-3.5 text-orange-400" />}
            <span>Regenerate</span>
          </button>
          <button
            onClick={handleCopySql}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5"
            title="Copy SQL DDL"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-teal-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
            <span>{copied ? 'Copied' : 'Copy SQL'}</span>
          </button>
          <button
            onClick={handleDownloadSql}
            className="px-3.5 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-teal-600/20"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download DDL</span>
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
        artifactName="Database Schema"
      />

      {/* View Switcher Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-1">
        <button
          onClick={() => setViewMode('tables')}
          className={`px-4 py-2 rounded-lg text-xs font-medium flex items-center gap-2 transition-colors ${
            viewMode === 'tables' 
              ? 'bg-slate-800 text-white font-semibold border-b-2 border-teal-500 rounded-b-none' 
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Table className="w-3.5 h-3.5 text-teal-400" />
          <span>Table Entities ({tables.length})</span>
        </button>

        <button
          onClick={() => setViewMode('er')}
          className={`px-4 py-2 rounded-lg text-xs font-medium flex items-center gap-2 transition-colors ${
            viewMode === 'er' 
              ? 'bg-slate-800 text-white font-semibold border-b-2 border-teal-500 rounded-b-none' 
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Link2 className="w-3.5 h-3.5 text-teal-400" />
          <span>Mermaid ER Diagram</span>
        </button>

        <button
          onClick={() => setViewMode('ddl')}
          className={`px-4 py-2 rounded-lg text-xs font-medium flex items-center gap-2 transition-colors ${
            viewMode === 'ddl' 
              ? 'bg-slate-800 text-white font-semibold border-b-2 border-teal-500 rounded-b-none' 
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileCode className="w-3.5 h-3.5 text-teal-400" />
          <span>SQL DDL Script</span>
        </button>
      </div>

      {loading ? (
        <div className="p-16 text-center text-slate-400 text-sm flex items-center justify-center gap-2 bg-[#131B2E] border border-slate-800 rounded-2xl">
          <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
          <span>Loading schema...</span>
        </div>
      ) : (!artifact || tables.length === 0) ? (
        <EmptyArtifactState
          title="Database Schema Not Generated Yet"
          description="Synthesize normalized relational database tables, attributes, primary/foreign key constraints, and entity-relationship models derived from project requirements."
          icon={Database}
          onGenerate={handleRegenerate}
          isGenerating={regenerating}
          generateLabel="Generate Database Schema"
        />
      ) : (
        <>
          {/* Tables View */}
          {viewMode === 'tables' && (
            <div className="space-y-6">
              {tables.map((table, tIdx) => (
                <div key={table.name || tIdx} className="bg-[#131B2E] border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
                  {/* Table Header */}
                  <div className="p-4 bg-[#162035] border-b border-slate-800 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-7 h-7 rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20 flex items-center justify-center font-mono text-xs font-bold">
                        T{tIdx + 1}
                      </div>
                      <div>
                        <h3 className="text-sm font-mono font-bold text-white tracking-wide">
                          {table.name}
                        </h3>
                        <p className="text-xs text-slate-400 mt-0.5">{table.description}</p>
                      </div>
                    </div>
                    <span className="text-[11px] font-mono text-slate-400 bg-slate-900 px-2.5 py-1 rounded-full border border-slate-800">
                      {table.columns?.length || 0} columns
                    </span>
                  </div>

                  {/* Columns Table */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[#0E1424] text-slate-400 font-mono text-[10px] uppercase tracking-wider border-b border-slate-800/80">
                        <tr>
                          <th className="py-2.5 px-4">Column Name</th>
                          <th className="py-2.5 px-4">Data Type</th>
                          <th className="py-2.5 px-4">Key</th>
                          <th className="py-2.5 px-4">Nullable</th>
                          <th className="py-2.5 px-4">Description</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                        {(table.columns || []).map((col, cIdx) => (
                          <tr key={col.name || cIdx} className="hover:bg-slate-800/30 transition-colors">
                            <td className="py-2.5 px-4 font-semibold text-slate-200">
                              {col.name}
                            </td>
                            <td className="py-2.5 px-4 text-orange-400">
                              {col.type}
                            </td>
                            <td className="py-2.5 px-4">
                              {col.pk ? (
                                <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">
                                  <Key className="w-2.5 h-2.5" /> PK
                                </span>
                              ) : col.fk ? (
                                <span className="inline-flex items-center gap-1 text-[10px] text-teal-400 bg-teal-500/10 px-1.5 py-0.5 rounded border border-teal-500/20" title={`References ${col.fk}`}>
                                  <Link2 className="w-2.5 h-2.5" /> FK &rarr; {col.fk}
                                </span>
                              ) : (
                                <span className="text-slate-600">-</span>
                              )}
                            </td>
                            <td className="py-2.5 px-4 text-slate-400">
                              {col.nullable ? 'YES' : 'NO'}
                            </td>
                            <td className="py-2.5 px-4 text-slate-400 font-sans text-xs">
                              {col.description}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Mermaid ER Diagram View */}
          {viewMode === 'er' && (
            <div className="bg-[#131B2E] border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="text-xs font-mono uppercase text-slate-400 tracking-wider font-semibold">
                  Entity-Relationship Visualizer
                </div>
                <span className="text-[11px] font-mono text-teal-400 bg-teal-500/10 px-2 py-0.5 rounded border border-teal-500/20">
                  Mermaid ER
                </span>
              </div>
              <div className="min-h-[350px] bg-[#0D1424] rounded-xl border border-slate-800/80 p-4 flex items-center justify-center overflow-x-auto">
                <MermaidViewer chart={mermaidEr} id="er-diagram" />
              </div>
            </div>
          )}

          {/* SQL DDL View */}
          {viewMode === 'ddl' && (
            <div className="bg-[#131B2E] border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="text-xs font-mono uppercase text-slate-400 tracking-wider font-semibold">
                  Standard SQL DDL Scripts
                </div>
                <button
                  onClick={handleCopySql}
                  className="text-xs text-teal-400 hover:text-teal-300 font-mono flex items-center gap-1"
                >
                  {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
              <pre className="p-4 bg-[#090D15] rounded-xl border border-slate-800 text-xs font-mono text-teal-300 overflow-x-auto leading-relaxed">
                {sqlDdl}
              </pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}
