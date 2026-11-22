import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Sparkles, 
  Check, 
  Loader2, 
  RefreshCw, 
  BookOpen, 
  Layers, 
  Database, 
  Code2, 
  Terminal, 
  CheckSquare, 
  ArrowRight, 
  Network, 
  Share2, 
  AlertCircle,
  FileCheck2,
  Workflow
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { projectApi } from '../api';

const artifactIcons = {
  srs: BookOpen,
  architecture: Layers,
  schema: Database,
  api: Code2,
  skeleton: Terminal,
  testcases: CheckSquare,
};

const artifactRoutes = {
  srs: '/srs',
  architecture: '/architecture',
  schema: '/database-schema',
  api: '/api-documentation',
  skeleton: '/backend-code',
  testcases: '/test-cases',
};

const artifactColors = {
  srs: 'from-orange-500/20 to-amber-500/10 text-orange-400 border-orange-500/30',
  architecture: 'from-blue-500/20 to-indigo-500/10 text-blue-400 border-blue-500/30',
  schema: 'from-teal-500/20 to-emerald-500/10 text-teal-400 border-teal-500/30',
  api: 'from-cyan-500/20 to-sky-500/10 text-cyan-400 border-cyan-500/30',
  skeleton: 'from-amber-500/20 to-yellow-500/10 text-amber-400 border-amber-500/30',
  testcases: 'from-emerald-500/20 to-teal-500/10 text-emerald-400 border-emerald-500/30',
};

export default function DashboardPage() {
  const { activeProjectId, activeProject, dashboardData, refreshDashboard, backendError, setIsNewProjectModalOpen } = useProject();
  const navigate = useNavigate();

  const [generatingAll, setGeneratingAll] = useState(false);
  const [activeJobId, setActiveJobId] = useState(null);
  const [jobProgress, setJobProgress] = useState(null);
  const [regeneratingItem, setRegeneratingItem] = useState(null);
  const [feedbackMessage, setFeedbackMessage] = useState(null);
  const [feedbackType, setFeedbackType] = useState('info'); // 'info' | 'success' | 'error'

  // Check for active job on mount or when activeProjectId changes
  useEffect(() => {
    let isMounted = true;
    const checkActiveJob = async () => {
      if (!activeProjectId) return;
      try {
        const res = await projectApi.getActiveJob(activeProjectId);
        if (isMounted && res && res.id && (res.status === 'running' || res.status === 'queued')) {
          setActiveJobId(res.id);
          setGeneratingAll(true);
          setJobProgress(res.progress || 0);
          setFeedbackType('info');
          setFeedbackMessage(res.message || "Artifact generation in progress...");
        }
      } catch (e) {
        // Silently ignore if inactive
      }
    };
    checkActiveJob();
    return () => { isMounted = false; };
  }, [activeProjectId]);

  // Poll active background generation job
  useEffect(() => {
    if (!activeJobId) return;

    let pollCount = 0;
    const interval = setInterval(async () => {
      try {
        pollCount++;
        const job = await projectApi.getJobStatus(activeJobId);
        if (!job) return;

        setJobProgress(job.progress || 0);
        if (job.message) {
          setFeedbackMessage(job.message);
        }

        // Incrementally refresh dashboard so counts increase live without refresh
        await refreshDashboard();

        if (job.status === 'completed') {
          clearInterval(interval);
          setActiveJobId(null);
          setGeneratingAll(false);
          setFeedbackType('success');
          setFeedbackMessage(job.message || "All artifacts generated successfully!");
          setTimeout(() => setFeedbackMessage(null), 5000);
        } else if (job.status === 'failed') {
          clearInterval(interval);
          setActiveJobId(null);
          setGeneratingAll(false);
          setFeedbackType('error');
          setFeedbackMessage(job.error || job.message || "Generation encountered errors. Partial artifacts saved.");
        }
      } catch (err) {
        console.error("Error polling job status:", err);
        if (pollCount > 180) { // Stop after 6 minutes of polling errors
          clearInterval(interval);
          setActiveJobId(null);
          setGeneratingAll(false);
          setFeedbackType('error');
          setFeedbackMessage("Lost connection to background job. Please refresh to check status.");
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [activeJobId, refreshDashboard]);

  const handleGenerateAll = async () => {
    if (!activeProjectId || generatingAll) return;
    setGeneratingAll(true);
    setFeedbackType('info');
    setFeedbackMessage("Starting background generation pipeline...");
    setJobProgress(0);
    try {
      const res = await projectApi.generateAllArtifacts(activeProjectId);
      if (res && res.job_id) {
        setActiveJobId(res.job_id);
        setFeedbackMessage(res.message || "Artifact generation started in background...");
      } else {
        await refreshDashboard();
        setFeedbackType('success');
        setFeedbackMessage("All artifacts generated successfully!");
        setGeneratingAll(false);
      }
    } catch (err) {
      console.error("Generate all error:", err);
      const errData = err.response?.data?.detail;
      if (err.response?.status === 409) {
        // Connect to already running job
        try {
          const activeJob = await projectApi.getActiveJob(activeProjectId);
          if (activeJob && activeJob.id) {
            setActiveJobId(activeJob.id);
            setFeedbackType('info');
            setFeedbackMessage("Connecting to existing active generation job...");
            return;
          }
        } catch (_) {}
      }
      setFeedbackType('error');
      const msg = typeof errData === 'string' ? errData : (errData?.message || "Error starting artifact generation.");
      setFeedbackMessage(msg);
      setGeneratingAll(false);
    }
  };

  const handleRegenerate = async (e, type) => {
    e.stopPropagation();
    if (!activeProjectId || regeneratingItem) return;
    setRegeneratingItem(type);
    try {
      await projectApi.regenerateArtifact(activeProjectId, type, {});
      await refreshDashboard();
    } catch (err) {
      console.error(err);
    } finally {
      setRegeneratingItem(null);
    }
  };

  const pipelineSteps = dashboardData?.pipeline_steps || [
    { id: 'upload', label: 'Upload', subtext: 'Upload document', state: 'pending' },
    { id: 'extraction', label: 'Extraction', subtext: 'Pending analysis', state: 'pending' },
    { id: 'rag_llm', label: 'RAG + LLM', subtext: 'Pending context', state: 'pending' },
    { id: 'generation', label: 'Generation', subtext: '0 of 6 artifacts', state: 'pending' },
    { id: 'ready', label: 'Ready', subtext: 'Pending generation', state: 'pending' },
  ];

  const statusChips = dashboardData?.status_chips || [
    { id: '1', label: 'Requirements Extracted', state: 'pending' },
    { id: '2', label: 'Functional Requirements Identified', state: 'pending' },
    { id: '3', label: 'Non-Functional Requirements Identified', state: 'pending' },
    { id: '4', label: 'Entities Identified', state: 'pending' },
    { id: '5', label: 'Modules Identified', state: 'pending' },
  ];

  const artifactCards = dashboardData?.artifact_cards || [
    { type: 'srs', title: 'SRS Document', description: 'Structured requirements spec generated from your upload.', count_label: 'Sections', count: 0, status: 'pending' },
    { type: 'architecture', title: 'Architecture', description: 'Suggested layered design - review before adopting.', count_label: 'Layers', count: 0, status: 'pending' },
    { type: 'schema', title: 'Database Schema', description: 'Entities and relationships derived from requirement text.', count_label: 'Tables', count: 0, status: 'pending' },
    { type: 'api', title: 'API Documentation', description: 'Endpoints, methods and sample payloads.', count_label: 'Endpoints', count: 0, status: 'pending' },
    { type: 'skeleton', title: 'Backend Skeleton', description: 'Starter FastAPI project - yours to extend, not final.', count_label: 'Files', count: 0, status: 'pending' },
    { type: 'testcases', title: 'Test Cases', description: 'Scenarios generated straight from the requirements.', count_label: 'Cases', count: 0, status: 'pending' },
  ];

  const graphSummary = dashboardData?.graph_summary || { nodes_count: 0, edges_count: 0 };

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-300">
      {/* Title & Header Action Row */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <h1 className="text-3xl font-serif font-bold text-white tracking-tight">
              {activeProject?.name || dashboardData?.project_name || 'Software Engineering Workspace'}
            </h1>
            {(activeProject?.status || dashboardData?.project_status) && (
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono uppercase bg-orange-500/10 text-orange-400 border border-orange-500/20 font-bold">
                {activeProject?.status || dashboardData?.project_status}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-400 max-w-2xl leading-relaxed">
            {activeProject?.description || (
              dashboardData?.uploaded_file 
                ? `Specification workspace grounded in ${dashboardData.uploaded_file}. Manage extraction, traceability, and multi-artifact generation.`
                : 'Upload requirement specifications to extract requirements, identify domain entities, and generate engineering artifacts.'
            )}
          </p>
        </div>

        {/* Generate All & Refresh Controls */}
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={() => refreshDashboard()}
            className="p-2.5 rounded-xl border border-slate-700/80 bg-[#131B2E] text-slate-400 hover:text-white hover:border-slate-600 transition-colors"
            title="Refresh dashboard state"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          <button
            onClick={handleGenerateAll}
            disabled={generatingAll}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white text-xs font-semibold tracking-wide shadow-lg shadow-orange-500/20 disabled:opacity-50 transition-all flex items-center gap-2 group cursor-pointer"
          >
            {generatingAll ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-white" />
                <span>Running Pipeline...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-orange-200 group-hover:scale-110 transition-transform" />
                <span>Generate All Artifacts</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Backend Not Reachable Alert */}
      {backendError && (
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            <div>
              <span className="font-semibold block text-sm">Backend not reachable</span>
              <span>{backendError}</span>
            </div>
          </div>
          <button
            onClick={() => refreshDashboard()}
            className="px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 text-xs font-semibold"
          >
            Retry Connection
          </button>
        </div>
      )}

      {feedbackMessage && (
        <div className={`p-3 rounded-xl text-xs flex items-center justify-between gap-2 border ${
          feedbackType === 'error'
            ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
            : feedbackType === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-teal-500/10 border-teal-500/30 text-teal-300'
        }`}>
          <div className="flex items-center gap-2">
            {generatingAll ? (
              <Loader2 className="w-4 h-4 shrink-0 animate-spin text-teal-400" />
            ) : feedbackType === 'error' ? (
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            ) : (
              <FileCheck2 className="w-4 h-4 shrink-0 text-emerald-400" />
            )}
            <span>{feedbackMessage}</span>
          </div>
          {generatingAll && jobProgress !== null && (
            <span className="font-mono text-[11px] text-teal-400 shrink-0 font-semibold">
              {Math.round(jobProgress)}%
            </span>
          )}
        </div>
      )}

      {/* PIPELINE STEPPER CARD (5 Connected Steps) */}
      <div className="bg-[#131B2E] border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="flex items-center justify-between relative z-10">
          {pipelineSteps.map((step, index) => {
            const isDone = step.state === 'done';
            const isInProgress = step.state === 'in_progress';
            const isError = step.state === 'error' || step.state === 'failed';
            const isPending = step.state === 'pending';

            return (
              <React.Fragment key={step.id}>
                {/* Step Item */}
                <div className="flex flex-col items-center text-center group min-w-[110px]">
                  {/* Indicator Box */}
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
                    isDone 
                      ? 'bg-teal-500/20 text-teal-400 border border-teal-500/40 shadow-sm shadow-teal-500/10' 
                      : isInProgress 
                        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/50 shadow-md shadow-amber-500/20 animate-pulse' 
                        : isError
                          ? 'bg-red-500/20 text-red-400 border border-red-500/50 shadow-md shadow-red-500/20'
                          : 'bg-slate-800/60 text-slate-500 border border-slate-700/60'
                  }`}>
                    {isDone ? (
                      <Check className="w-4 h-4 stroke-[2.5]" />
                    ) : isInProgress ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : isError ? (
                      <AlertCircle className="w-4 h-4 text-red-400" />
                    ) : (
                      <span className="text-xs font-mono">-</span>
                    )}
                  </div>

                  {/* Step Label */}
                  <div className={`mt-2.5 text-xs font-semibold ${
                    isDone ? 'text-slate-200' : isInProgress ? 'text-amber-300 font-bold' : isError ? 'text-red-400 font-semibold' : 'text-slate-400'
                  }`}>
                    {step.label}
                  </div>

                  {/* Step Subtext */}
                  <div className={`text-[11px] font-mono mt-0.5 truncate max-w-[130px] ${
                    isError ? 'text-red-400/90' : 'text-slate-400'
                  }`}>
                    {step.subtext}
                  </div>
                </div>

                {/* Connecting Line between steps */}
                {index < pipelineSteps.length - 1 && (
                  <div className="flex-1 h-[2px] mx-3 mb-6 relative">
                    <div className="absolute inset-0 bg-slate-800 rounded" />
                    <div className={`absolute inset-0 rounded transition-all duration-500 ${
                      isDone ? 'bg-teal-500/70' : isError ? 'bg-red-500/40' : 'bg-transparent'
                    }`} />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* STATUS CHIPS ROW */}
      <div className="flex flex-wrap items-center gap-2.5">
        {statusChips.map((chip) => {
          const isDone = chip.state === 'done';
          const isInProgress = chip.state === 'in_progress';
          const isError = chip.state === 'error' || chip.state === 'failed';

          return (
            <div
              key={chip.id}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                isDone 
                  ? 'bg-slate-900/80 border-slate-800 text-slate-300' 
                  : isInProgress 
                    ? 'bg-amber-500/10 border-amber-500/30 text-amber-300' 
                    : isError
                      ? 'bg-red-500/10 border-red-500/30 text-red-400'
                      : 'bg-slate-900/40 border-slate-800/60 text-slate-400'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${
                isDone 
                  ? 'bg-teal-400' 
                  : isInProgress 
                    ? 'bg-amber-400 animate-ping' 
                    : isError
                      ? 'bg-red-400'
                      : 'bg-slate-600'
              }`} />
              <span>{chip.label}</span>
            </div>
          );
        })}
      </div>

      {/* 3x2 ARTIFACT CARD GRID */}
      <div>
        <div className="text-xs font-mono uppercase text-slate-400 tracking-wider mb-4 font-semibold">
          Generated Engineering Artifacts (6)
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {artifactCards.map((card) => {
            const Icon = artifactIcons[card.type] || BookOpen;
            const route = artifactRoutes[card.type] || '/';
            const colorClass = artifactColors[card.type] || 'text-orange-400';
            const isRegenerating = regeneratingItem === card.type || card.status === 'generating';

            return (
              <div
                key={card.type}
                onClick={() => navigate(route)}
                className="bg-[#131B2E] hover:bg-[#162138] border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 shadow-lg transition-all duration-200 cursor-pointer flex flex-col justify-between group relative overflow-hidden"
              >
                {/* Top Section: Icon Tile + Title + Description */}
                <div>
                  <div className="flex items-center justify-between mb-3.5">
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${colorClass} border flex items-center justify-center shadow-sm`}>
                      <Icon className="w-5 h-5" />
                    </div>

                    {/* Status Pill / Regenerate Action */}
                    <div className="flex items-center gap-2">
                      {isRegenerating ? (
                        <div className="flex items-center gap-1.5 text-[11px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          <span>Generating</span>
                        </div>
                      ) : (card.status === 'completed' || card.count > 0) ? (
                        <div className="flex items-center gap-2">
                          <span className="flex items-center gap-1 text-[10px] font-mono text-teal-400 bg-teal-500/10 border border-teal-500/20 px-2 py-0.5 rounded-full">
                            <Check className="w-2.5 h-2.5 stroke-[2.5]" /> Ready
                          </span>
                          <button
                            onClick={(e) => handleRegenerate(e, card.type)}
                            className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white text-[11px] flex items-center gap-1"
                            title="Regenerate this artifact"
                          >
                            <RefreshCw className="w-3 h-3" />
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={(e) => handleRegenerate(e, card.type)}
                          className="px-2.5 py-1 rounded-lg bg-orange-500/10 hover:bg-orange-500/20 text-orange-400 border border-orange-500/30 text-[11px] font-medium flex items-center gap-1 transition-colors"
                          title="Generate this artifact"
                        >
                          <Sparkles className="w-3 h-3" />
                          <span>Generate</span>
                        </button>
                      )}
                    </div>
                  </div>

                  <h3 className="text-base font-semibold text-slate-100 group-hover:text-orange-300 transition-colors">
                    {card.title}
                  </h3>
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed line-clamp-2">
                    {card.description}
                  </p>
                </div>

                {/* Bottom Row: Count Label & Metric + Arrow */}
                <div className="mt-5 pt-3.5 border-t border-slate-800/80 flex items-center justify-between text-xs">
                  <div className="font-mono text-slate-400">
                    <span className="text-slate-400">{card.count_label}:</span>{' '}
                    <span className="text-slate-200 font-semibold">{card.count}</span>
                  </div>

                  <div className="flex items-center gap-1 text-slate-400 group-hover:text-orange-400 transition-colors">
                    <span className="text-[11px] font-medium">View</span>
                    <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* KNOWLEDGE GRAPH SUMMARY CARD */}
      <div 
        onClick={() => navigate('/knowledge-graph')}
        className="bg-gradient-to-r from-[#131B2E] to-[#152037] border border-slate-800 hover:border-slate-700 rounded-2xl p-6 shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 cursor-pointer group"
      >
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-orange-500/10 border border-orange-500/30 text-orange-400 flex items-center justify-center shrink-0">
            <Network className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs font-mono uppercase text-orange-400 font-semibold tracking-wider">
              Traceability & Graph
            </div>
            <h4 className="text-base font-semibold text-white mt-0.5">
              Knowledge Graph & Traceability Matrix
            </h4>
            <p className="text-xs text-slate-400 mt-0.5">
              Explore interconnected nodes: Requirement &rarr; Module &rarr; API &rarr; Entity &rarr; Test Case.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-6 shrink-0">
          <div className="flex items-center gap-4 font-mono text-xs">
            <div className="text-center px-3 py-1.5 bg-slate-900/60 rounded-xl border border-slate-800">
              <div className="text-slate-400 text-[10px] uppercase">Nodes</div>
              <div className="text-white font-bold text-sm">{graphSummary.nodes_count}</div>
            </div>
            <div className="text-center px-3 py-1.5 bg-slate-900/60 rounded-xl border border-slate-800">
              <div className="text-slate-400 text-[10px] uppercase">Edges</div>
              <div className="text-white font-bold text-sm">{graphSummary.edges_count}</div>
            </div>
          </div>

          <div className="flex items-center gap-1.5 text-xs font-semibold text-orange-400 group-hover:text-orange-300">
            <span>Explore Graph</span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>
      </div>
    </div>
  );
}
