import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  FileText, 
  BookOpen, 
  Layers, 
  Database, 
  Code2, 
  Terminal, 
  CheckSquare, 
  Network, 
  Sparkles, 
  Plus, 
  ChevronDown, 
  FolderKanban,
  Check,
  Trash2,
  Edit2,
  Settings
} from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { projectApi } from '../../api';

export default function Sidebar() {
  const { 
    projects, 
    activeProjectId, 
    activeProject, 
    dashboardData, 
    testCasesCount, 
    availableArtifacts = {},
    selectProject, 
    refreshProjects,
    setIsNewProjectModalOpen 
  } = useProject();
  
  const [isSwitcherOpen, setIsSwitcherOpen] = useState(false);
  const location = useLocation();

  const handleRenameProject = async (e, projectId, currentName) => {
    e.stopPropagation();
    const newName = window.prompt("Enter new project name:", currentName);
    if (!newName || !newName.trim() || newName.trim() === currentName) return;
    try {
      await projectApi.update(projectId, { name: newName.trim() });
      await refreshProjects();
    } catch (err) {
      alert("Failed to rename project.");
    }
  };

  const handleDeleteProject = async (e, projectId, projectName) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete project "${projectName}"? This action cannot be undone.`)) return;
    try {
      await projectApi.delete(projectId);
      await refreshProjects();
    } catch (err) {
      alert("Failed to delete project.");
    }
  };

  const completedArtifacts = dashboardData?.total_artifacts_generated ?? activeProject?.artifact_count ?? 0;
  const getArtifactMeta = (type) => dashboardData?.artifact_cards?.find(c => c.type === type);
  const reqCount = dashboardData?.graph_summary?.requirement_count;

  const workspaceNav = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { 
      name: 'Requirements', 
      path: '/requirements', 
      icon: FileText, 
      isAvailable: (reqCount > 0),
      badge: reqCount > 0 ? reqCount : undefined 
    },
    { 
      name: 'SRS', 
      path: '/srs', 
      icon: BookOpen, 
      isAvailable: availableArtifacts?.srs 
    },
    { 
      name: 'Architecture', 
      path: '/architecture', 
      icon: Layers, 
      isAvailable: availableArtifacts?.architecture 
    },
    { 
      name: 'Database Schema', 
      path: '/database-schema', 
      icon: Database, 
      isAvailable: availableArtifacts?.schema 
    },
    { 
      name: 'API Documentation', 
      path: '/api-documentation', 
      icon: Code2, 
      isAvailable: availableArtifacts?.api 
    },
    { 
      name: 'Backend Code', 
      path: '/backend-code', 
      icon: Terminal, 
      isAvailable: availableArtifacts?.skeleton 
    },
    { 
      name: 'Test Cases', 
      path: '/test-cases', 
      icon: CheckSquare, 
      isAvailable: availableArtifacts?.testcases,
      badge: testCasesCount > 0 ? testCasesCount : undefined 
    },
    { 
      name: 'Knowledge Graph', 
      path: '/knowledge-graph', 
      icon: Network, 
      isAvailable: availableArtifacts?.graph 
    },
  ];

  const assistNav = [
    { name: 'AI Query Assistant', path: '/query-assistant', icon: Sparkles },
    { name: 'Settings & API Keys', path: '/settings', icon: Settings },
  ];

  return (
    <aside className="w-[255px] min-w-[255px] bg-white border-r border-slate-200 flex flex-col justify-between h-screen fixed top-0 left-0 z-40 select-none">
      {/* Top Header & Project Card */}
      <div className="p-4 space-y-4">
        {/* Logo Tile */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center shadow-md shadow-blue-500/20 font-bold !text-white text-base tracking-tight">
            R+C
          </div>
          <div>
            <div className="font-semibold text-slate-900 text-base tracking-tight leading-tight">
              Req-to-Code
            </div>
            <div className="text-xs text-slate-500 font-medium">
              AI Assistant
            </div>
          </div>
        </div>

        {/* ACTIVE PROJECT Card */}
        <div className="relative">
          <button
            onClick={() => setIsSwitcherOpen(!isSwitcherOpen)}
            className="w-full text-left bg-slate-50 hover:bg-slate-100/80 transition-colors border border-slate-200 rounded-xl p-3 group"
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-mono tracking-wider text-slate-500 font-semibold">
                ACTIVE PROJECT
              </span>
              <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isSwitcherOpen ? 'rotate-180' : ''}`} />
            </div>
            <div className="font-semibold text-sm text-slate-900 truncate mt-1">
              {activeProject?.name || dashboardData?.project_name || 'Select a project'}
            </div>
            {dashboardData?.uploaded_file && (
              <div className="text-[11px] text-slate-500 truncate mt-0.5 flex items-center gap-1">
                <FileText className="w-3 h-3 text-blue-600 shrink-0" />
                <span className="truncate">{dashboardData.uploaded_file}</span>
              </div>
            )}
            <div className="text-[11px] font-mono text-slate-500 mt-0.5 flex items-center justify-between">
              <span>{completedArtifacts} artifacts</span>
              {(activeProject?.status || dashboardData?.project_status) && (
                <span className="text-[9px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-200/80 text-slate-700 border border-slate-300">
                  {activeProject?.status || dashboardData?.project_status}
                </span>
              )}
            </div>
          </button>

          {/* Project Switcher Popover */}
          {isSwitcherOpen && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-xl shadow-xl py-1.5 z-50 max-h-56 overflow-y-auto">
              <div className="px-3 py-1 text-[10px] font-mono uppercase text-slate-400 tracking-wider">
                Switch Project
              </div>
              {projects.length === 0 ? (
                <div className="px-3 py-2 text-xs text-slate-400">No projects yet</div>
              ) : (
                projects.map((p) => (
                  <div
                    key={p.id}
                    onClick={() => {
                      selectProject(p.id);
                      setIsSwitcherOpen(false);
                    }}
                    className={`w-full px-3 py-2 text-xs flex items-center justify-between hover:bg-slate-50 transition-colors cursor-pointer group ${p.id === activeProjectId ? 'bg-blue-50/70' : ''}`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      {p.id === activeProjectId && (
                        <Check className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                      )}
                      <span className={`truncate ${p.id === activeProjectId ? 'text-blue-700 font-semibold' : 'text-slate-700'}`}>{p.name}</span>
                    </div>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity ml-2 shrink-0">
                      <button
                        onClick={(e) => handleRenameProject(e, p.id, p.name)}
                        className="p-1 hover:text-blue-600 text-slate-400 transition-colors rounded"
                        title="Rename project"
                      >
                        <Edit2 className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => handleDeleteProject(e, p.id, p.name)}
                        className="p-1 hover:text-red-500 text-slate-400 transition-colors rounded"
                        title="Delete project"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))
              )}
              <div className="border-t border-slate-100 mt-1 pt-1 px-1">
                <button
                  onClick={() => {
                    setIsSwitcherOpen(false);
                    setIsNewProjectModalOpen(true);
                  }}
                  className="w-full text-left px-2 py-1.5 text-xs text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded flex items-center gap-1.5 font-medium"
                >
                  <Plus className="w-3.5 h-3.5" /> Create Project
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Section: WORKSPACE */}
        <div className="space-y-1 pt-1">
          <div className="px-3 pb-1 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
            WORKSPACE
          </div>
          <nav className="space-y-0.5">
            {workspaceNav.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <NavLink
                  key={item.name}
                  to={item.path}
                  className={`relative flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all ${
                    isActive 
                      ? 'bg-blue-50 text-blue-700 font-semibold shadow-xs' 
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  }`}
                >
                  {isActive && (
                    <span className="w-1 bg-blue-600 rounded-r-md h-5 absolute left-0" />
                  )}
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                    <span className="truncate">{item.name}</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {item.isAvailable && !item.badge && (
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-sm" title="Artifact ready" />
                    )}
                    {item.badge !== undefined && (
                      <span className="px-1.5 py-0.5 rounded-full text-[10px] font-mono bg-blue-100 text-blue-700 border border-blue-200">
                        {item.badge}
                      </span>
                    )}
                  </div>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Section: ASSIST */}
        <div className="space-y-1 pt-2">
          <div className="px-3 pb-1 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
            ASSIST
          </div>
          <nav className="space-y-0.5">
            {assistNav.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <NavLink
                  key={item.name}
                  to={item.path}
                  className={`relative flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all ${
                    isActive 
                      ? 'bg-blue-50 text-blue-700 font-semibold shadow-xs' 
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  }`}
                >
                  {isActive && (
                    <span className="w-1 bg-blue-600 rounded-r-md h-5 absolute left-0" />
                  )}
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                    <span>{item.name}</span>
                  </div>
                </NavLink>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Bottom Action: + New Project */}
      <div className="p-4 border-t border-slate-200">
        <button
          onClick={() => setIsNewProjectModalOpen(true)}
          className="w-full py-2.5 px-3 border border-dashed border-slate-300 hover:border-blue-500 rounded-xl text-slate-600 hover:text-blue-700 hover:bg-blue-50/50 transition-all text-xs font-medium flex items-center justify-center gap-2 group"
        >
          <Plus className="w-4 h-4 text-slate-400 group-hover:text-blue-600 transition-colors" />
          <span>New project</span>
        </button>
      </div>
    </aside>
  );
}
