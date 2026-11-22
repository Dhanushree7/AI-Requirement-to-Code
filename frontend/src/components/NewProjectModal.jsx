import React, { useState, useRef } from 'react';
import { X, Upload, FileText, CheckCircle2, Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { projectApi } from '../api';

export default function NewProjectModal() {
  const { isNewProjectModalOpen, setIsNewProjectModalOpen, refreshProjects, selectProject } = useProject();

  const [projectName, setProjectName] = useState('');
  const [projectDescription, setProjectDescription] = useState('');
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [createdProject, setCreatedProject] = useState(null);

  // Live checklist steps
  const [checklist, setChecklist] = useState({
    uploaded: 'pending', // pending | in_progress | done
    extracted: 'pending',
    functional: 'pending',
    nonFunctional: 'pending',
    entities: 'pending',
    modules: 'pending'
  });

  const fileInputRef = useRef(null);

  if (!isNewProjectModalOpen) return null;

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const resetState = () => {
    setProjectName('');
    setProjectDescription('');
    setFile(null);
    setIsProcessing(false);
    setError(null);
    setCreatedProject(null);
    setChecklist({
      uploaded: 'pending',
      extracted: 'pending',
      functional: 'pending',
      nonFunctional: 'pending',
      entities: 'pending',
      modules: 'pending'
    });
  };

  const handleClose = () => {
    if (isProcessing) return;
    resetState();
    setIsNewProjectModalOpen(false);
  };

  const handleRetryAnalysis = async () => {
    if (!createdProject || isProcessing) return;

    setIsProcessing(true);
    setError(null);

    try {
      setChecklist(prev => ({
        ...prev,
        uploaded: 'done',
        extracted: 'done',
        functional: 'in_progress',
        nonFunctional: 'pending',
        entities: 'pending',
        modules: 'pending'
      }));

      await projectApi.analyzeRequirements(createdProject.id);

      setChecklist(prev => ({
        ...prev,
        functional: 'done',
        nonFunctional: 'done',
        entities: 'done',
        modules: 'done'
      }));

      // Success: refresh and select project
      await refreshProjects();
      selectProject(createdProject.id);

      setTimeout(() => {
        setIsProcessing(false);
        setIsNewProjectModalOpen(false);
        resetState();
      }, 1200);

    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || "Requirement analysis retry failed. Please try again.");
      setIsProcessing(false);
      refreshProjects();
    }
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!projectName.trim()) {
      setError("Please provide a project name.");
      return;
    }

    setIsProcessing(true);
    setError(null);

    let project = createdProject;

    try {
      // 1. Create Project (if not already created)
      if (!project) {
        setChecklist(prev => ({ ...prev, uploaded: 'in_progress' }));
        project = await projectApi.create({
          name: projectName.trim(),
          description: projectDescription.trim() || undefined
        });
        setCreatedProject(project);
      }

      // 2. Upload file if provided and not yet uploaded
      if (file && checklist.uploaded !== 'done') {
        setChecklist(prev => ({ ...prev, uploaded: 'in_progress' }));
        await projectApi.upload(project.id, file);
        setChecklist(prev => ({ ...prev, uploaded: 'done', extracted: 'in_progress' }));
      } else if (!file) {
        setChecklist(prev => ({ ...prev, uploaded: 'done' }));
      }

      // 3. Trigger requirement analysis
      if (file || checklist.uploaded === 'done') {
        setChecklist(prev => ({ ...prev, extracted: 'done', functional: 'in_progress' }));
        await projectApi.analyzeRequirements(project.id);
        
        setChecklist(prev => ({ 
          ...prev, 
          functional: 'done', 
          nonFunctional: 'done', 
          entities: 'done', 
          modules: 'done' 
        }));
      }

      // Success: refresh and select project
      await refreshProjects();
      selectProject(project.id);

      setTimeout(() => {
        setIsProcessing(false);
        setIsNewProjectModalOpen(false);
        resetState();
      }, 1200);

    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || "Failed to create and analyze project.");
      setIsProcessing(false);
      refreshProjects();
    }
  };

  const checklistItems = [
    { key: 'uploaded', label: 'Document Uploaded & Validated' },
    { key: 'extracted', label: 'Document Text Extracted' },
    { key: 'functional', label: 'Functional Requirements Identified' },
    { key: 'nonFunctional', label: 'Non-Functional Requirements Identified' },
    { key: 'entities', label: 'Domain Entities Identified' },
    { key: 'modules', label: 'System Modules Identified' }
  ];

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#111726] border border-slate-700/80 rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-[#0E131F]">
          <div>
            <h2 className="text-lg font-serif font-bold text-white tracking-tight">Create New Project</h2>
            <p className="text-xs text-slate-400 mt-0.5">Upload a requirement specification (PDF/DOCX) to begin analysis.</p>
          </div>
          <button
            onClick={handleClose}
            disabled={isProcessing}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-30"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {error && (
            <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex flex-col gap-2.5">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span className="flex-1 leading-relaxed">{error}</span>
              </div>
              {createdProject && (
                <div className="flex items-center justify-between pt-2 border-t border-red-500/20 text-slate-300">
                  <span className="text-[11px] text-slate-400">
                    Project and document are safely saved. You can retry analysis directly without recreating.
                  </span>
                  <button
                    type="button"
                    onClick={handleRetryAnalysis}
                    disabled={isProcessing}
                    className="px-3 py-1.5 rounded-lg bg-orange-500 hover:bg-orange-600 text-white font-medium text-xs flex items-center gap-1.5 shadow-sm transition-colors disabled:opacity-50 shrink-0 ml-2"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isProcessing ? 'animate-spin' : ''}`} />
                    Retry Analysis
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Project Name */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-mono">
              Project Name <span className="text-orange-400">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g., Intelligent Library Management System"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              disabled={isProcessing}
              required
              className="w-full bg-[#162035] border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-orange-500 transition-colors disabled:opacity-50"
            />
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider font-mono">
              Description (Optional)
            </label>
            <textarea
              rows={2}
              placeholder="Brief context or goals for this software project..."
              value={projectDescription}
              onChange={(e) => setProjectDescription(e.target.value)}
              disabled={isProcessing}
              className="w-full bg-[#162035] border border-slate-700 rounded-xl px-4 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-orange-500 transition-colors resize-none disabled:opacity-50"
            />
          </div>

          {/* File Upload Drag & Drop */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-mono">
              Software Requirement Document (PDF, DOCX, TXT)
            </label>
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => !isProcessing && fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
                isDragging 
                  ? 'border-orange-500 bg-orange-500/10' 
                  : file 
                    ? 'border-teal-500/50 bg-teal-500/5' 
                    : 'border-slate-700 hover:border-slate-600 bg-[#141C2E]'
              } ${isProcessing ? 'pointer-events-none opacity-60' : ''}`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc,.txt,.md"
                onChange={handleFileChange}
                className="hidden"
              />
              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-teal-500/20 text-teal-400 border border-teal-500/30 flex items-center justify-center">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div className="text-left">
                    <div className="text-sm font-medium text-slate-200 truncate max-w-xs">{file.name}</div>
                    <div className="text-xs text-slate-400">{(file.size / 1024).toFixed(1)} KB</div>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="w-10 h-10 mx-auto rounded-lg bg-slate-800 text-slate-400 flex items-center justify-center">
                    <Upload className="w-5 h-5 text-orange-400" />
                  </div>
                  <div className="text-sm font-medium text-slate-300">
                    Click to browse or drag and drop document
                  </div>
                  <div className="text-xs text-slate-500">
                    PDF, DOCX, or TXT up to 25MB
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Live Progress Checklist (Shown during analysis) */}
          {isProcessing && (
            <div className="p-4 bg-[#0E1424] rounded-xl border border-slate-800 space-y-2 animate-in fade-in duration-200">
              <div className="text-xs font-mono uppercase text-slate-400 tracking-wider mb-2 font-semibold">
                Pipeline Analysis Status
              </div>
              <div className="space-y-1.5">
                {checklistItems.map(item => {
                  const state = checklist[item.key];
                  return (
                    <div key={item.key} className="flex items-center gap-2 text-xs">
                      {state === 'done' ? (
                        <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0" />
                      ) : state === 'in_progress' ? (
                        <Loader2 className="w-4 h-4 text-amber-400 animate-spin shrink-0" />
                      ) : (
                        <div className="w-4 h-4 rounded-full border border-slate-700 shrink-0 flex items-center justify-center text-[9px] text-slate-500">
                          -
                        </div>
                      )}
                      <span className={`${state === 'done' ? 'text-slate-200' : state === 'in_progress' ? 'text-amber-300 font-medium' : 'text-slate-500'}`}>
                        {item.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={handleClose}
              disabled={isProcessing}
              className="px-4 py-2.5 rounded-xl text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-40"
            >
              Cancel
            </button>
            {createdProject ? (
              <button
                type="button"
                onClick={handleRetryAnalysis}
                disabled={isProcessing}
                className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white shadow-lg shadow-orange-500/20 disabled:opacity-50 transition-all flex items-center gap-2"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Retrying Analysis...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4" />
                    Retry Analysis
                  </>
                )}
              </button>
            ) : (
              <button
                type="submit"
                disabled={isProcessing || !projectName.trim()}
                className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white shadow-lg shadow-orange-500/20 disabled:opacity-50 transition-all flex items-center gap-2"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Analyzing Pipeline...
                  </>
                ) : (
                  'Upload & Analyze'
                )}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
