import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  Sparkles, 
  FileText, 
  BookOpen, 
  Layers, 
  Database, 
  Code2, 
  CheckSquare, 
  Sun, 
  Moon, 
  ArrowRight,
  ShieldCheck,
  CheckCircle2
} from 'lucide-react';

/**
 * Shared SaaS-grade Authentication Layout
 * Includes responsive split layout, theme synchronization, and platform branding showcase.
 */
export default function AuthLayout({ children, activeTab = 'login' }) {
  const [isDark, setIsDark] = useState(() => {
    return localStorage.getItem('req_to_code_theme') === 'dark' || 
           document.documentElement.classList.contains('dark');
  });

  useEffect(() => {
    const saved = localStorage.getItem('req_to_code_theme');
    if (saved === 'dark') {
      setIsDark(true);
      document.documentElement.classList.add('dark');
    } else if (saved === 'light') {
      setIsDark(false);
      document.documentElement.classList.remove('dark');
    }
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

  const featureHighlights = [
    {
      icon: Sparkles,
      title: 'AI-Powered Requirement Analysis',
      desc: 'Automatic parsing, categorization, and domain validation from raw documents.'
    },
    {
      icon: BookOpen,
      title: 'Automated SRS Generation',
      desc: 'Production-ready specifications with structured functional & quality metrics.'
    },
    {
      icon: Layers,
      title: 'System Architecture Design',
      desc: 'Requirement-driven pattern justification with interactive Mermaid diagrams.'
    },
    {
      icon: Database,
      title: 'Database Schema Generation',
      desc: 'Normalized relational schemas with strict entity constraints and relations.'
    },
    {
      icon: Code2,
      title: 'API Documentation',
      desc: 'Standardized endpoint specs, payload schemas, and response definitions.'
    },
    {
      icon: CheckSquare,
      title: 'Test Case Generation',
      desc: 'Comprehensive end-to-end test suites with full requirement traceability.'
    }
  ];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0B0F17] text-slate-900 dark:text-slate-100 flex flex-col justify-between selection:bg-blue-600 selection:text-white transition-colors">
      {/* Top Application Bar */}
      <header className="w-full h-16 border-b border-slate-200/80 dark:border-slate-800 bg-white/80 dark:bg-[#0B0F17]/80 backdrop-blur-md px-6 sm:px-10 flex items-center justify-between sticky top-0 z-20">
        {/* Brand Logo & Name */}
        <Link to="/login" className="flex items-center gap-3 group focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 via-indigo-600 to-navy-900 flex items-center justify-center shadow-md shadow-blue-500/20 text-white font-bold text-base tracking-tight transition-transform group-hover:scale-105">
            R+C
          </div>
          <div>
            <div className="font-semibold text-slate-900 dark:text-white text-base tracking-tight leading-tight flex items-center gap-1.5">
              <span>ReqToCode AI</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200/60 dark:border-blue-800">
                v1.0
              </span>
            </div>
            <div className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
              Intelligent Requirement Engineering Platform
            </div>
          </div>
        </Link>

        {/* Right Navigation Controls */}
        <div className="flex items-center gap-3">
          {/* Phase 1 Pill */}
          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-300 font-medium">
            <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
            <span>Phase 1: Auth UI</span>
          </div>

          {/* Theme Toggle Button */}
          <button
            onClick={toggleTheme}
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            className="p-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white hover:bg-slate-100 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors cursor-pointer shadow-xs"
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDark ? (
              <Sun className="w-4 h-4 text-amber-400" />
            ) : (
              <Moon className="w-4 h-4 text-slate-600" />
            )}
          </button>

          {/* Direct link to preview workspace */}
          <Link
            to="/"
            className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 hover:border-blue-500 bg-white dark:bg-slate-800 text-xs font-medium text-slate-700 dark:text-slate-200 hover:text-blue-600 dark:hover:text-blue-400 transition-all shadow-xs"
            title="Preview existing Workspace"
          >
            <span>Workspace Preview</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </header>

      {/* Main Authentication Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-10 flex items-center justify-center">
        <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          
          {/* LEFT: Platform Branding & Value Proposition Hero (Desktop & Tablet) */}
          <div className="auth-branding-panel lg:col-span-7 flex flex-col justify-between rounded-3xl bg-gradient-to-br from-[#0F172A] via-[#111C38] to-[#1E293B] !text-white p-8 sm:p-10 lg:p-12 shadow-2xl shadow-blue-950/20 border border-slate-800/80 relative overflow-hidden">
            {/* Subtle radial background decorative glow */}
            <div className="absolute top-0 right-0 -mr-20 -mt-20 w-80 h-80 bg-blue-600/15 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-80 h-80 bg-indigo-600/15 rounded-full blur-3xl pointer-events-none" />

            <div className="relative z-10 space-y-6">
              {/* Top Subtitle Badge */}
              <div className="auth-badge inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/15 border border-blue-400/30 text-blue-300 text-xs font-mono font-medium tracking-wide">
                <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
                <span>INTELLIGENT REQUIREMENT WORKSPACE</span>
              </div>

              {/* Main Headline */}
              <div className="space-y-3">
                <h1 
                  className="auth-hero-title text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight !text-white leading-tight font-serif-title"
                  style={{ color: '#FFFFFF' }}
                >
                  Transform Requirements into Software Artifacts
                </h1>
                <p 
                  className="auth-hero-desc text-sm sm:text-base !text-slate-200 leading-relaxed max-w-xl font-normal"
                  style={{ color: '#E2E8F0' }}
                >
                  ReqToCode AI is a professional, domain-independent engineering platform that accelerates software development by turning natural requirements into verified specifications, system architectures, database schemas, and runnable code.
                </p>
              </div>

              {/* 6 Core Feature Highlights Grid */}
              <div className="pt-2 grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {featureHighlights.map((feat, idx) => {
                  const Icon = feat.icon;
                  return (
                    <div 
                      key={idx}
                      className="auth-feature-card p-3.5 rounded-xl bg-white/[0.05] hover:bg-white/[0.08] border border-white/[0.1] transition-colors flex items-start gap-3"
                    >
                      <div className="auth-feature-icon-wrapper p-2 rounded-lg bg-blue-500/20 text-blue-400 shrink-0 mt-0.5">
                        <Icon className="w-4 h-4 text-blue-400" />
                      </div>
                      <div className="space-y-0.5 min-w-0">
                        <h2 
                          className="auth-feature-title text-xs font-semibold !text-white tracking-tight"
                          style={{ color: '#FFFFFF' }}
                        >
                          {feat.title}
                        </h2>
                        <p 
                          className="auth-feature-desc text-[11px] !text-slate-300 leading-normal"
                          style={{ color: '#CBD5E1' }}
                        >
                          {feat.desc}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Bottom Assurance Bar */}
              <div className="pt-4 border-t border-slate-700/60 flex flex-wrap items-center justify-between gap-3 text-xs auth-bottom-text">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span style={{ color: '#E2E8F0' }}>100% Domain-Independent Engineering</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span style={{ color: '#E2E8F0' }}>Complete Requirement Traceability</span>
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT: Modern SaaS Auth Card */}
          <div className="lg:col-span-5 w-full">
            <div className="bg-white dark:bg-[#111827] rounded-3xl border border-slate-200/90 dark:border-slate-800 shadow-xl shadow-slate-200/60 dark:shadow-none p-6 sm:p-9 relative">
              {/* Tab Navigation between Login & Signup */}
              <div className="flex items-center p-1 rounded-xl bg-slate-100 dark:bg-slate-800/80 mb-6 text-xs font-medium">
                <Link
                  to="/login"
                  className={`flex-1 py-2 text-center rounded-lg transition-all ${
                    activeTab === 'login'
                      ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 font-semibold shadow-xs'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  Sign In
                </Link>
                <Link
                  to="/signup"
                  className={`flex-1 py-2 text-center rounded-lg transition-all ${
                    activeTab === 'signup'
                      ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 font-semibold shadow-xs'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  Create Account
                </Link>
              </div>

              {/* Injected Form Component */}
              {children}

              {/* Bottom Notice: Phase 1 Preview Status */}
              <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800/80 text-center">
                <p className="text-[11px] text-slate-400 dark:text-slate-500">
                  <span className="font-semibold text-slate-500 dark:text-slate-400">Phase 1 Preview:</span> Form validation and UI flows are fully functional. Backend identity provider & user sessions connect in Phase 2.
                </p>
              </div>
            </div>
          </div>

        </div>
      </main>

      {/* Footer */}
      <footer className="w-full py-4 px-6 border-t border-slate-200/60 dark:border-slate-800/60 text-center text-xs text-slate-500 dark:text-slate-400 flex flex-col sm:flex-row items-center justify-between max-w-7xl mx-auto">
        <div>
          © {new Date().getFullYear()} ReqToCode AI. All rights reserved.
        </div>
        <div className="flex items-center gap-4 mt-2 sm:mt-0 text-[11px]">
          <span className="hover:text-slate-700 dark:hover:text-slate-200 cursor-pointer">Security Overview</span>
          <span>•</span>
          <span className="hover:text-slate-700 dark:hover:text-slate-200 cursor-pointer">Documentation</span>
          <span>•</span>
          <Link to="/" className="text-blue-600 dark:text-blue-400 hover:underline">Go to Workspace</Link>
        </div>
      </footer>
    </div>
  );
}
