import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bell, Sun, Moon, Cpu, FileText, LogOut } from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { useAuth } from '../../context/AuthContext';
import { projectApi } from '../../api';

const routeTitleMap = {
  '/': 'Dashboard',
  '/requirements': 'Requirements',
  '/srs': 'SRS',
  '/architecture': 'Architecture',
  '/database-schema': 'Database Schema',
  '/api-documentation': 'API Documentation',
  '/backend-code': 'Backend Code',
  '/test-cases': 'Test Cases',
  '/knowledge-graph': 'Knowledge Graph',
  '/query-assistant': 'AI Query Assistant',
};

export default function TopBar() {
  const { activeProject, dashboardData } = useProject();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [isDark, setIsDark] = useState(() => {
    return localStorage.getItem('req_to_code_theme') === 'dark';
  });
  const [llmStatus, setLlmStatus] = useState(null); // {provider, model, success, error}

  useEffect(() => {
    const saved = localStorage.getItem('req_to_code_theme');
    if (saved === 'dark') {
      setIsDark(true);
      document.documentElement.classList.add('dark');
    } else {
      setIsDark(false);
      document.documentElement.classList.remove('dark');
    }
  }, []);

  useEffect(() => {
    projectApi.getLlmHealth()
      .then(data => setLlmStatus(data))
      .catch(() => setLlmStatus({ provider: 'unknown', model: 'unknown', success: false, error: 'Unreachable' }));
  }, []);

  const toggleTheme = () => {
    const nextDark = !isDark;
    setIsDark(nextDark);
    if (nextDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('req_to_code_theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('req_to_code_theme', 'light');
    }
  };

  const projectName = activeProject?.name || dashboardData?.project_name || 'Req-to-Code';
  const currentPage = routeTitleMap[location.pathname] || 'Dashboard';

  return (
    <header className="h-16 border-b border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-[#0B0F17]/90 backdrop-blur-md sticky top-0 z-30 px-8 flex items-center justify-between transition-colors">
      {/* Breadcrumb & Project Document Context */}
      <div className="flex items-center gap-3 text-sm">
        <div className="flex items-center gap-2">
          <span className="text-slate-500 dark:text-slate-400 font-normal">
            {projectName}
          </span>
          <span className="text-slate-400 dark:text-slate-600">/</span>
          <span className="text-slate-900 dark:text-slate-100 font-semibold tracking-tight">
            {currentPage}
          </span>
        </div>

        {dashboardData?.uploaded_file && (
          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-[11px] text-slate-700 dark:text-slate-300 font-mono">
            <FileText className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
            <span className="max-w-[200px] truncate" title={dashboardData.uploaded_file}>
              {dashboardData.uploaded_file}
            </span>
          </div>
        )}
      </div>

      {/* Right Controls: LLM Status + Theme Toggle + User Avatar */}
      <div className="flex items-center gap-3">
        {/* Backend & AI Connection Status Badge */}
        {llmStatus && (
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border ${
              llmStatus.success
                ? 'border-emerald-500/30 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400'
                : 'border-rose-500/30 bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-400'
            }`}
            title={
              llmStatus.success
                ? `AI Engine: Connected (${llmStatus.provider} / ${llmStatus.model})`
                : `AI Engine: Offline (${llmStatus.error || 'unreachable'})`
            }
          >
            <Cpu className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
            <span className={`w-1.5 h-1.5 rounded-full ${llmStatus.success ? 'bg-emerald-500' : 'bg-rose-500'}`} />
            <span className="font-semibold tracking-wider">
              {llmStatus.success ? 'ONLINE' : 'OFFLINE'}
            </span>
            <span className="text-[10px] text-slate-500 dark:text-slate-400 font-sans">
              ({llmStatus.provider})
            </span>
          </div>
        )}

        {/* Light / Dark Mode Toggle */}
        <button
          onClick={toggleTheme}
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
          className="p-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 hover:bg-slate-100 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors flex items-center justify-center cursor-pointer shadow-xs"
          title={isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {isDark ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-slate-600" />
          )}
        </button>

        {/* User Profile & Logout */}
        <div className="flex items-center gap-2.5 pl-2 border-l border-slate-200 dark:border-slate-800">
          <div 
            className="w-8 h-8 rounded-full bg-blue-600 text-white font-semibold text-xs flex items-center justify-center shadow-xs select-none"
            title={user?.email ? `${user.full_name} (${user.email})` : "User"}
          >
            {user?.full_name ? user.full_name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() : 'SE'}
          </div>
          <div className="hidden lg:flex flex-col text-left">
            <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 leading-tight">
              {user?.full_name || 'Engineer'}
            </span>
            <span className="text-[10px] text-slate-400 leading-tight truncate max-w-[120px]">
              {user?.email || ''}
            </span>
          </div>
          <button
            onClick={() => {
              logout();
              navigate('/login');
            }}
            title="Log out of session"
            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
