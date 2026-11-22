import React, { useState, useEffect } from 'react';
import { 
  BookOpen, 
  Download, 
  Edit3, 
  Save, 
  RotateCcw, 
  History, 
  Check, 
  FileText, 
  AlertCircle, 
  Loader2,
  Sparkles,
  RefreshCw
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { projectApi } from '../api';
import MarkdownViewer from '../components/MarkdownViewer';
import EmptyArtifactState from '../components/EmptyArtifactState';

export default function SrsPage() {
  const { activeProjectId } = useProject();
  const [artifact, setArtifact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(null);
  const [saving, setSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [showVersions, setShowVersions] = useState(false);

  const loadArtifact = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      const data = await projectApi.getArtifact(activeProjectId, 'srs');
      setArtifact(data);
      setEditedContent(data?.content);
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
    if (!activeProjectId || isGenerating) return;
    setIsGenerating(true);
    try {
      const updated = await projectApi.regenerateArtifact(activeProjectId, 'srs', {});
      setArtifact(updated);
      setEditedContent(updated?.content);
    } catch (err) {
      console.error(err);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!activeProjectId || saving) return;
    setSaving(true);
    try {
      const updated = await projectApi.updateArtifact(activeProjectId, 'srs', {
        content: editedContent,
        changelog: `Manual developer revision (v${(artifact?.current_version || 1) + 1})`
      });
      setArtifact(updated);
      setIsEditing(false);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const handleRestore = async (versionNumber) => {
    if (!confirm(`Restore version ${versionNumber}?`)) return;
    try {
      const restored = await projectApi.restoreVersion(activeProjectId, 'srs', versionNumber);
      setArtifact(restored);
      setEditedContent(restored.content);
      setShowVersions(false);
    } catch (err) {
      console.error(err);
    }
  };

  const extractSections = (raw) => {
    if (!raw) return [];
    if (Array.isArray(raw.sections) && raw.sections.length > 0) {
      return raw.sections;
    }
    if (Array.isArray(raw)) {
      return raw.map((item, idx) => ({
        id: `SEC-${idx + 1}`,
        title: item.title || `Section ${idx + 1}`,
        content: item.content || (typeof item === 'object' ? JSON.stringify(item, null, 2) : String(item))
      }));
    }
    if (typeof raw === 'object') {
      return Object.entries(raw)
        .filter(([k]) => k !== 'title' && k !== 'disclaimer' && k !== 'sections')
        .map(([k, v], idx) => ({
          id: `SEC-${idx + 1}`,
          title: `${idx + 1}.0 ${k.replace(/([a-z0-9])([A-Z])/g, '$1 $2').replace(/[_-]/g, ' ').trim()}`,
          content: typeof v === 'string' ? v : (typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v))
        }));
    }
    return [];
  };

  const sections = extractSections(editedContent || artifact?.content);

  const handleExportMarkdown = () => {
    if (!sections.length) return;
    let md = `# ${editedContent?.title || artifact?.content?.title || 'Software Requirements Specification'}\n\n`;
    sections.forEach(s => {
      md += `## ${s.title}\n\n${s.content}\n\n`;
    });

    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `SRS_Specification_${activeProjectId.slice(0, 8)}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleExportPdf = () => {
    window.print();
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-blue-50 text-blue-700 border border-blue-200 font-semibold">
              System Specification
            </span>
            <span className="text-xs font-mono text-slate-500">
              {artifact?.current_version ? `Version ${artifact.current_version}` : 'Specification'} &bull; {sections.length} Sections
            </span>
          </div>
          <h1 className="text-3xl font-serif font-bold text-slate-900 tracking-tight mt-1">
            Software Requirements Specification (SRS)
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Comprehensive software requirements specification generated from your project requirements.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5">
          {sections.length > 0 && (
            <button
              onClick={() => setShowVersions(!showVersions)}
              className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5"
              title="Version history"
            >
              <History className="w-4 h-4 text-slate-400" />
              <span>History ({artifact?.versions?.length || 1})</span>
            </button>
          )}

          <button
            onClick={handleRegenerate}
            disabled={isGenerating}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5 disabled:opacity-50"
            title="Regenerate SRS"
          >
            {isGenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin text-orange-400" /> : <RefreshCw className="w-3.5 h-3.5 text-orange-400" />}
            <span>Regenerate</span>
          </button>

          {sections.length > 0 && (
            <>
              <button
                onClick={handleExportMarkdown}
                className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5"
                title="Export as Markdown"
              >
                <Download className="w-4 h-4 text-teal-400" />
                <span>Export MD</span>
              </button>

              <button
                onClick={handleExportPdf}
                className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5"
                title="Export as PDF"
              >
                <FileText className="w-4 h-4 text-orange-400" />
                <span>Export PDF</span>
              </button>

              {isEditing ? (
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-emerald-600/20"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  <span>Save Changes</span>
                </button>
              ) : (
                <button
                  onClick={() => setIsEditing(true)}
                  className="px-4 py-2 rounded-xl bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-orange-500/20"
                >
                  <Edit3 className="w-4 h-4" />
                  <span>Edit Document</span>
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Version History Drawer */}
      {showVersions && (
        <div className="bg-[#131B2E] border border-slate-700/80 rounded-2xl p-4 shadow-xl space-y-2">
          <div className="text-xs font-mono uppercase text-slate-400 tracking-wider font-semibold">
            Version History
          </div>
          <div className="divide-y divide-slate-800">
            {(artifact?.versions || []).map((v) => (
              <div key={v.id} className="py-2.5 flex items-center justify-between text-xs">
                <div>
                  <span className="font-mono font-bold text-orange-400">v{v.version_number}</span>
                  <span className="text-slate-400 ml-2">{v.changelog || 'Automated generation'}</span>
                  <span className="text-slate-500 text-[10px] ml-2">
                    {new Date(v.created_at).toLocaleTimeString()}
                  </span>
                </div>
                {v.version_number !== artifact?.current_version && (
                  <button
                    onClick={() => handleRestore(v.version_number)}
                    className="text-xs text-teal-400 hover:text-teal-300 font-mono flex items-center gap-1"
                  >
                    <RotateCcw className="w-3 h-3" /> Restore
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Document Body Card */}
      {loading ? (
        <div className="bg-[#131B2E] border border-slate-800 rounded-2xl p-12 text-center text-slate-400 text-sm flex items-center justify-center gap-2 shadow-2xl">
          <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
          <span>Loading SRS document...</span>
        </div>
      ) : sections.length === 0 ? (
        <EmptyArtifactState
          title="SRS Document Not Generated Yet"
          description="Synthesize a structured requirements specification covering functional scope, external interfaces, non-functional attributes, and traceability matrices."
          icon={BookOpen}
          onGenerate={handleRegenerate}
          isGenerating={isGenerating}
          generateLabel="Generate SRS Document"
        />
      ) : (
        <div className="bg-[#131B2E] border border-slate-800 rounded-2xl p-8 shadow-2xl space-y-8">
          {sections.map((section, idx) => (
            <div key={section.id || idx} className="space-y-3 pb-6 border-b border-slate-800/80 last:border-b-0">
              <h2 className="text-lg font-serif font-bold text-white flex items-center gap-2">
                <span>{section.title}</span>
              </h2>

              {isEditing ? (
                <textarea
                  rows={5}
                  value={section.content}
                  onChange={(e) => {
                    const newSections = [...sections];
                    newSections[idx].content = e.target.value;
                    setEditedContent({ ...editedContent, sections: newSections });
                  }}
                  className="w-full bg-[#162035] border border-slate-700 rounded-xl p-3.5 text-xs text-slate-200 focus:outline-none focus:border-orange-500 leading-relaxed font-sans"
                />
              ) : (
                <MarkdownViewer content={section.content} className="pl-1" />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
