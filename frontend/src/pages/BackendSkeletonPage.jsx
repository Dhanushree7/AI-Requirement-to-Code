import React, { useState, useEffect } from 'react';
import { 
  Terminal, 
  Download, 
  Copy, 
  Check, 
  FileCode, 
  Folder, 
  FolderOpen, 
  CheckCircle2, 
  AlertTriangle, 
  RefreshCw, 
  Loader2, 
  AlertCircle,
  Sparkles
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { projectApi } from '../api';
import EmptyArtifactState from '../components/EmptyArtifactState';

export default function BackendSkeletonPage() {
  const { activeProjectId } = useProject();
  const [skeletonData, setSkeletonData] = useState(null);
  const [selectedFileIndex, setSelectedFileIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const loadSkeleton = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      const data = await projectApi.getBackendSkeleton(activeProjectId);
      setSkeletonData(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadZip = async () => {
    if (!activeProjectId || downloading) return;
    setDownloading(true);
    try {
      await projectApi.downloadBackendZip(activeProjectId);
    } catch (err) {
      console.error('Failed to download backend zip archive:', err);
    } finally {
      setDownloading(false);
    }
  };

  useEffect(() => {
    loadSkeleton();
  }, [activeProjectId]);

  const handleRegenerate = async () => {
    if (!activeProjectId || regenerating) return;
    setRegenerating(true);
    try {
      await projectApi.regenerateArtifact(activeProjectId, 'skeleton', {});
      await loadSkeleton();
    } catch (err) {
      console.error(err);
    } finally {
      setRegenerating(false);
    }
  };

  const extractFiles = (data) => {
    if (!data) return [];
    if (Array.isArray(data.files)) return data.files;
    if (data.files && typeof data.files === 'object') {
      return Object.entries(data.files).map(([path, content]) => ({
        path,
        content: typeof content === 'string' ? content : JSON.stringify(content, null, 2),
        language: path.endsWith('.py') ? 'python' : 'text',
        is_valid_python: path.endsWith('.py') ? true : null
      }));
    }
    return [];
  };

  const files = extractFiles(skeletonData);
  const currentFile = files[selectedFileIndex] || files[0] || null;

  const handleCopyCode = () => {
    if (!currentFile) return;
    navigator.clipboard.writeText(currentFile.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-amber-500/10 text-amber-400 border border-amber-500/20">
              Generated Backend Scaffolding
            </span>
            <span className="text-xs font-mono text-slate-400">
              {files.length} Project Files
            </span>
          </div>
          <h1 className="text-3xl font-serif font-bold text-white tracking-tight mt-1">
            Backend Skeleton Code
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Starter FastAPI project based on your requirements and schema - yours to extend, not final.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="px-3.5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5 disabled:opacity-50"
            title="Regenerate Backend Code"
          >
            {regenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin text-orange-400" /> : <RefreshCw className="w-3.5 h-3.5 text-orange-400" />}
            <span>Regenerate</span>
          </button>
          {files.length > 0 && (
            <button
              onClick={handleDownloadZip}
              disabled={downloading}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white text-xs font-semibold flex items-center gap-2 shadow-lg shadow-orange-500/20 cursor-pointer disabled:opacity-50"
              title="Download Backend Starter as ZIP"
            >
              {downloading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              <span>{downloading ? 'Downloading...' : 'Download as ZIP'}</span>
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="p-16 text-center text-slate-400 text-sm flex items-center justify-center gap-2 bg-[#131B2E] border border-slate-800 rounded-2xl">
          <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
          <span>Loading backend skeleton...</span>
        </div>
      ) : files.length === 0 ? (
        <EmptyArtifactState
          title="Backend Skeleton Not Generated Yet"
          description="Synthesize an executable backend codebase with routing, database models, schemas, and unit test suites tailored to the project requirements."
          icon={Terminal}
          onGenerate={handleRegenerate}
          isGenerating={regenerating}
          generateLabel="Generate Backend Code"
        />
      ) : (
        <>
          {/* Validation Pipeline Summary Grid (Step 4 UI) */}
      {skeletonData?.validation && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          {/* Compilation Card */}
          <div className="bg-[#131B2E] border border-slate-800/90 rounded-xl p-3.5 flex flex-col justify-between">
            <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">Compilation</div>
            <div className="flex items-center gap-1.5 mt-2 font-mono text-xs font-semibold">
              {skeletonData.validation.compiled ? (
                <span className="text-teal-400 flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> Compiled</span>
              ) : (
                <span className="text-red-400 flex items-center gap-1"><AlertTriangle className="w-3.5 h-3.5" /> Error</span>
              )}
            </div>
          </div>

          {/* Import Card */}
          <div className="bg-[#131B2E] border border-slate-800/90 rounded-xl p-3.5 flex flex-col justify-between">
            <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">App Import</div>
            <div className="flex items-center gap-1.5 mt-2 font-mono text-xs font-semibold">
              {skeletonData.validation.imported ? (
                <span className="text-teal-400 flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> app.main OK</span>
              ) : (
                <span className="text-red-400 flex items-center gap-1"><AlertTriangle className="w-3.5 h-3.5" /> Failed</span>
              )}
            </div>
          </div>

          {/* Endpoints Card */}
          <div className="bg-[#131B2E] border border-slate-800/90 rounded-xl p-3.5 flex flex-col justify-between">
            <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">Endpoints</div>
            <div className="flex items-center gap-1.5 mt-2 font-mono text-xs font-semibold text-white">
              <span className="text-amber-400">{skeletonData.validation.endpoints_found ?? 0}</span>
              <span className="text-slate-500">of</span>
              <span>{skeletonData.validation.endpoints_expected ?? 0}</span>
            </div>
          </div>

          {/* Test Suite Card */}
          <div className="bg-[#131B2E] border border-slate-800/90 rounded-xl p-3.5 flex flex-col justify-between">
            <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">Tests Passed</div>
            <div className="flex items-center gap-1.5 mt-2 font-mono text-xs font-semibold text-white">
              <span className="text-teal-400">{skeletonData.validation.tests_passed ?? 0} passed</span>
              {skeletonData.validation.tests_failed > 0 && (
                <span className="text-red-400">({skeletonData.validation.tests_failed} failed)</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* AST Verification Banner */}
      <div className="flex items-center justify-between text-xs bg-[#131B2E] border border-slate-800 rounded-xl px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="font-mono text-slate-400">Python AST Verification:</span>
          {skeletonData?.all_syntax_valid ? (
            <span className="inline-flex items-center gap-1 font-mono text-teal-400 font-bold bg-teal-500/10 px-2 py-0.5 rounded border border-teal-500/20">
              <CheckCircle2 className="w-3.5 h-3.5" /> Syntax Valid
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 font-mono text-red-400 font-bold bg-red-500/10 px-2 py-0.5 rounded border border-red-500/20">
              <AlertTriangle className="w-3.5 h-3.5" /> Syntax Error Detected
            </span>
          )}
        </div>
        <span className="text-[11px] font-mono text-slate-500">
          Validated via ast.parse
        </span>
      </div>

      {/* IDE Code Viewer Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 bg-[#131B2E] border border-slate-800 rounded-2xl overflow-hidden shadow-2xl min-h-[550px]">
        {/* Left: File Tree Navigator */}
        <div className="lg:col-span-1 border-r border-slate-800 p-4 bg-[#0E1424] space-y-2">
          <div className="text-xs font-mono uppercase text-slate-400 tracking-wider font-semibold px-2 mb-3">
            FastAPI Project Tree
          </div>

          <div className="space-y-1">
            {files.map((file, idx) => {
              const isSelected = selectedFileIndex === idx;
              return (
                <button
                  key={file.path || idx}
                  onClick={() => setSelectedFileIndex(idx)}
                  className={`w-full px-3 py-2 rounded-xl text-left font-mono text-xs flex items-center justify-between transition-colors ${
                    isSelected
                      ? 'bg-orange-500/15 text-orange-400 font-bold border border-orange-500/30'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                  }`}
                >
                  <div className="flex items-center gap-2 truncate">
                    <FileCode className={`w-3.5 h-3.5 ${isSelected ? 'text-orange-400' : 'text-slate-500'}`} />
                    <span className="truncate">{file.path}</span>
                  </div>

                  {file.is_valid_python !== null && file.is_valid_python !== undefined && (
                    <span className={`w-1.5 h-1.5 rounded-full ${file.is_valid_python ? 'bg-teal-400' : 'bg-red-400'}`} title={file.is_valid_python ? "Valid AST" : file.syntax_error} />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Code Viewer */}
        <div className="lg:col-span-3 flex flex-col bg-[#090D15]">
          {/* File Tab Header */}
          <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-[#0E1424]">
            <div className="flex items-center gap-2 font-mono text-xs">
              <span className="text-slate-400">{currentFile?.path || 'main.py'}</span>
              <span className="text-slate-600">&bull;</span>
              <span className="text-orange-400 uppercase text-[10px] bg-slate-900 px-2 py-0.5 rounded">
                {currentFile?.language || 'python'}
              </span>
            </div>

            <button
              onClick={handleCopyCode}
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono flex items-center gap-1.5 transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-teal-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
              <span>{copied ? 'Copied' : 'Copy Code'}</span>
            </button>
          </div>

          {/* Syntax Code Body */}
          <div className="flex-1 p-5 overflow-auto max-h-[500px]">
            {loading ? (
              <div className="p-12 text-center text-slate-500 text-xs flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-orange-400" />
                <span>Loading source code...</span>
              </div>
            ) : (
              <pre className="text-xs font-mono leading-relaxed text-slate-200 whitespace-pre">
                <code>{currentFile?.content}</code>
              </pre>
            )}
          </div>
        </div>
      </div>
    </>
  )}
</div>
);
}
