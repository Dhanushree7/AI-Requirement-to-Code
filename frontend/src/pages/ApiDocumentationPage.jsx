import React, { useState, useEffect } from 'react';
import { 
  Code2, 
  Download, 
  Copy, 
  Check, 
  RefreshCw, 
  Lock, 
  Unlock, 
  ChevronDown, 
  AlertCircle, 
  Loader2 
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { projectApi } from '../api';
import EmptyArtifactState from '../components/EmptyArtifactState';

const methodColors = {
  GET: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  POST: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  PUT: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  PATCH: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30',
  DELETE: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
};

export default function ApiDocumentationPage() {
  const { activeProjectId } = useProject();
  const [artifact, setArtifact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedIndex, setExpandedIndex] = useState(0);
  const [filterMethod, setFilterMethod] = useState('ALL');
  const [regenerating, setRegenerating] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadArtifact = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      const data = await projectApi.getArtifact(activeProjectId, 'api');
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
      const updated = await projectApi.regenerateArtifact(activeProjectId, 'api', {});
      setArtifact(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setRegenerating(false);
    }
  };

  const extractEndpoints = (data) => {
    if (!data) return [];
    if (Array.isArray(data.endpoints) && data.endpoints.length > 0) return data.endpoints;
    if (data.paths && typeof data.paths === 'object') {
      const eps = [];
      Object.entries(data.paths).forEach(([path, methods]) => {
        if (typeof methods === 'object' && methods !== null) {
          Object.entries(methods).forEach(([method, op]) => {
            if (['get', 'post', 'put', 'delete', 'patch'].includes(method.toLowerCase())) {
              eps.push({
                path,
                method: method.toUpperCase(),
                summary: op?.summary || `${method.toUpperCase()} ${path}`,
                description: op?.description || '',
                tag: op?.tags?.[0] || 'Default',
                auth_required: !!(op?.security || data.components?.securitySchemes),
                parameters: Array.isArray(op?.parameters) ? op.parameters : [],
                request_body: op?.requestBody || {},
                responses: op?.responses ? Object.entries(op.responses).map(([code, r]) => ({
                  code,
                  description: typeof r === 'string' ? r : (r?.description || '')
                })) : [{ code: '200', description: 'Success' }]
              });
            }
          });
        }
      });
      return eps;
    }
    return [];
  };

  const content = artifact?.content || {};
  const endpoints = extractEndpoints(content);

  const filteredEndpoints = endpoints.filter(e => {
    if (filterMethod === 'ALL') return true;
    return e.method === filterMethod;
  });

  const handleExportOpenApi = () => {
    const openApiDoc = {
      openapi: '3.0.3',
      info: {
        title: content.title || 'Req-to-Code API Documentation',
        version: '1.0.0',
        description: 'Auto-generated API specification from software requirements.'
      },
      paths: {}
    };

    endpoints.forEach(ep => {
      if (!openApiDoc.paths[ep.path]) openApiDoc.paths[ep.path] = {};
      openApiDoc.paths[ep.path][ep.method.toLowerCase()] = {
        summary: ep.summary,
        tags: [ep.tag || 'Default'],
        parameters: ep.parameters || [],
        responses: (ep.responses || []).reduce((acc, r) => {
          acc[r.code] = { description: r.description };
          return acc;
        }, {})
      };
    });

    const blob = new Blob([JSON.stringify(openApiDoc, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `openapi_${activeProjectId.slice(0, 8)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleExportYaml = () => {
    let yaml = 'openapi: "3.0.3"\ninfo:\n';
    yaml += `  title: "${content.title || 'Req-to-Code API Documentation'}"\n`;
    yaml += '  version: "1.0.0"\n';
    yaml += '  description: "Auto-generated API specification from software requirements."\npaths:\n';
    endpoints.forEach(ep => {
      yaml += `  "${ep.path}":\n`;
      yaml += `    ${ep.method.toLowerCase()}:\n`;
      yaml += `      summary: "${ep.summary || ''}"\n`;
      yaml += `      tags:\n        - "${ep.tag || 'Default'}"\n`;
      yaml += `      responses:\n`;
      (ep.responses || []).forEach(r => {
        yaml += `        "${r.code}":\n          description: "${r.description || ''}"\n`;
      });
    });

    const blob = new Blob([yaml], { type: 'text/yaml;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `openapi_${activeProjectId.slice(0, 8)}.yaml`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleExportMarkdown = () => {
    let md = `# ${content.title || 'RESTful API Documentation'}\n\n`;
    md += `*Generated for project \`${activeProjectId.slice(0, 8)}\`*\n\n`;
    endpoints.forEach(ep => {
      md += `### \`${ep.method}\` ${ep.path}\n\n`;
      md += `**Summary:** ${ep.summary || 'N/A'}\n\n`;
      md += `**Tag:** ${ep.tag || 'General'}\n\n`;
      if (ep.parameters && ep.parameters.length > 0) {
        md += `**Parameters:**\n\n| Name | In | Type | Required | Description |\n|---|---|---|---|---|\n`;
        ep.parameters.forEach(p => {
          md += `| \`${p.name}\` | ${p.in} | ${p.type} | ${p.required ? 'Yes' : 'No'} | ${p.description || ''} |\n`;
        });
        md += '\n';
      }
      if (ep.request_body) {
        md += `**Request Body:**\n\`\`\`json\n${JSON.stringify(ep.request_body, null, 2)}\n\`\`\`\n\n`;
      }
      if (ep.responses && ep.responses.length > 0) {
        md += `**Responses:**\n\n| Status Code | Description |\n|---|---|\n`;
        ep.responses.forEach(r => {
          md += `| \`${r.code}\` | ${r.description} |\n`;
        });
        md += '\n';
      }
      md += '---\n\n';
    });

    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `api_documentation_${activeProjectId.slice(0, 8)}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              RESTful API Specification
            </span>
            <span className="text-xs font-mono text-slate-400">
              {endpoints.length} REST Endpoints
            </span>
          </div>
          <h1 className="text-3xl font-serif font-bold text-white tracking-tight mt-1">
            API Documentation
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            REST endpoints, authentication, request parameters, and response schemas.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5 disabled:opacity-50"
          >
            {regenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin text-orange-400" /> : <RefreshCw className="w-3.5 h-3.5 text-orange-400" />}
            <span>Regenerate</span>
          </button>
          <button
            onClick={handleExportOpenApi}
            className="px-3 py-2 rounded-xl bg-cyan-600/80 hover:bg-cyan-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-cyan-600/20"
            title="Export as OpenAPI JSON"
          >
            <Download className="w-3.5 h-3.5" />
            <span>JSON</span>
          </button>
          <button
            onClick={handleExportYaml}
            className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5"
            title="Export as YAML"
          >
            <Download className="w-3.5 h-3.5 text-teal-400" />
            <span>YAML</span>
          </button>
          <button
            onClick={handleExportMarkdown}
            className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5"
            title="Export as Markdown"
          >
            <Download className="w-3.5 h-3.5 text-orange-400" />
            <span>Markdown</span>
          </button>
        </div>
      </div>

      {/* Method Filters */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-1">
        {['ALL', 'GET', 'POST', 'PUT', 'DELETE'].map(method => (
          <button
            key={method}
            onClick={() => setFilterMethod(method)}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-colors ${
              filterMethod === method
                ? 'bg-slate-800 text-white border-b-2 border-cyan-500 rounded-b-none'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {method}
          </button>
        ))}
      </div>

      {/* Endpoints Accordion List */}
      {loading ? (
        <div className="p-16 text-center text-slate-400 text-sm flex items-center justify-center gap-2 bg-[#131B2E] border border-slate-800 rounded-2xl">
          <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
          <span>Loading API documentation...</span>
        </div>
      ) : (!artifact || endpoints.length === 0) ? (
        <EmptyArtifactState
          title="API Specification Not Generated Yet"
          description="Synthesize OpenAPI 3.0 compliant REST endpoints, request schemas, parameters, and response models derived from project requirements."
          icon={Code2}
          onGenerate={handleRegenerate}
          isGenerating={regenerating}
          generateLabel="Generate API Specification"
        />
      ) : (
        <div className="space-y-3">
          {filteredEndpoints.map((ep, idx) => {
            const isExpanded = expandedIndex === idx;
            const badgeClass = methodColors[ep.method] || 'bg-slate-800 text-slate-300';

            return (
              <div 
                key={idx} 
                className="bg-[#131B2E] border border-slate-800 rounded-2xl overflow-hidden shadow-lg transition-all"
              >
                {/* Accordion Header */}
                <button
                  onClick={() => setExpandedIndex(isExpanded ? null : idx)}
                  className="w-full p-4 flex items-center justify-between text-left hover:bg-[#162138] transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className={`px-2.5 py-1 rounded text-xs font-mono font-bold border ${badgeClass}`}>
                      {ep.method}
                    </span>
                    <span className="font-mono text-sm font-semibold text-slate-100">
                      {ep.path}
                    </span>
                    <span className="text-xs text-slate-400 hidden sm:inline">
                      &bull; {ep.summary}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    {ep.auth_required ? (
                      <span className="flex items-center gap-1 text-[11px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                        <Lock className="w-3 h-3" /> JWT
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[11px] font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                        <Unlock className="w-3 h-3 text-slate-500" /> Public
                      </span>
                    )}
                    <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                  </div>
                </button>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="p-5 border-t border-slate-800 bg-[#0E1424] space-y-4 animate-in fade-in duration-150">
                    <div>
                      <div className="text-[11px] font-mono uppercase text-slate-400 font-semibold">Summary & Scope</div>
                      <p className="text-xs text-slate-300 mt-1">{ep.summary}</p>
                    </div>

                    {/* Parameters */}
                    {ep.parameters && ep.parameters.length > 0 && (
                      <div className="space-y-1.5">
                        <div className="text-[11px] font-mono uppercase text-slate-400 font-semibold">Parameters</div>
                        <div className="bg-[#131B2E] rounded-xl border border-slate-800 overflow-hidden">
                          <table className="w-full text-left text-xs font-mono">
                            <thead className="bg-slate-900 text-slate-500 text-[10px] uppercase">
                              <tr>
                                <th className="p-2">Name</th>
                                <th className="p-2">In</th>
                                <th className="p-2">Type</th>
                                <th className="p-2">Required</th>
                                <th className="p-2 font-sans">Description</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800 text-[11px]">
                              {ep.parameters.map((p, pIdx) => (
                                <tr key={pIdx}>
                                  <td className="p-2 text-cyan-400 font-bold">{p.name}</td>
                                  <td className="p-2 text-slate-400">{p.in}</td>
                                  <td className="p-2 text-orange-400">{p.type}</td>
                                  <td className="p-2 text-slate-300">{p.required ? 'YES' : 'NO'}</td>
                                  <td className="p-2 font-sans text-xs text-slate-400">{p.description}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Request Body Example */}
                    {ep.request_body && (
                      <div className="space-y-1">
                        <div className="text-[11px] font-mono uppercase text-slate-400 font-semibold">Sample Request Payload</div>
                        <pre className="p-3 bg-[#0B0F17] rounded-xl border border-slate-800 text-xs font-mono text-emerald-400 overflow-x-auto">
                          {JSON.stringify(ep.request_body, null, 2)}
                        </pre>
                      </div>
                    )}

                    {/* Responses */}
                    {ep.responses && (
                      <div className="space-y-1.5">
                        <div className="text-[11px] font-mono uppercase text-slate-400 font-semibold">Status Responses</div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {ep.responses.map((resp, rIdx) => (
                            <div key={rIdx} className="p-3 bg-[#131B2E] rounded-xl border border-slate-800 space-y-1 text-xs">
                              <div className="flex items-center gap-2">
                                <span className={`px-2 py-0.5 rounded font-mono font-bold text-[11px] ${
                                  resp.code < 300 
                                    ? 'bg-emerald-500/20 text-emerald-400' 
                                    : 'bg-red-500/20 text-red-400'
                                }`}>
                                  HTTP {resp.code}
                                </span>
                                <span className="text-slate-300 font-medium">{resp.description}</span>
                              </div>
                              {resp.example && (
                                <pre className="p-2 bg-[#0B0F17] rounded text-[11px] font-mono text-slate-300 overflow-x-auto">
                                  {JSON.stringify(resp.example, null, 2)}
                                </pre>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
