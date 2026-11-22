import React, { useState, useEffect } from 'react';
import { ShieldCheck, AlertCircle, RefreshCw, Cpu, Server } from 'lucide-react';
import { projectApi } from '../api';

export default function SettingsPage() {
  const [health, setHealth] = useState(null);
  const [providerStatus, setProviderStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  const loadStatus = async () => {
    setLoading(true);
    setErr(null);
    try {
      const [h, p] = await Promise.all([
        projectApi.getLlmHealth().catch(e => ({ success: false, error: e.message })),
        projectApi.getProviderStatus().catch(e => ({ configured: false, error: e.message }))
      ]);
      setHealth(h);
      setProviderStatus(p);
    } catch (e) {
      setErr("Backend connection failed.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const isConnected = health?.success === true;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-serif font-bold text-white tracking-tight">System & AI Settings</h1>
        <p className="text-sm text-slate-400 mt-1">Configured AI provider, model selection, and backend connection status.</p>
      </div>

      {err && (
        <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{err}</span>
        </div>
      )}

      <div className="p-6 rounded-2xl bg-[#111827] border border-slate-800 space-y-6">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${isConnected ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border border-rose-500/20 text-rose-400'}`}>
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">LLM Provider Configuration</h2>
              <p className="text-xs text-slate-400">Read directly from backend/.env</p>
            </div>
          </div>
          <button
            onClick={loadStatus}
            disabled={loading}
            className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-2 border border-slate-700 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-[#090D16] border border-slate-800/80">
            <span className="text-[11px] font-mono text-slate-500 block mb-1">PROVIDER</span>
            <span className="text-sm font-semibold text-slate-200 uppercase tracking-wide">
              {health?.provider || providerStatus?.provider || 'Unknown'}
            </span>
          </div>
          <div className="p-4 rounded-xl bg-[#090D16] border border-slate-800/80">
            <span className="text-[11px] font-mono text-slate-500 block mb-1">MODEL</span>
            <span className="text-sm font-mono text-slate-200">
              {health?.model || providerStatus?.model || 'Unknown'}
            </span>
          </div>
          <div className="p-4 rounded-xl bg-[#090D16] border border-slate-800/80">
            <span className="text-[11px] font-mono text-slate-500 block mb-1">STATUS</span>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-rose-400'}`} />
              <span className={`text-xs font-semibold ${isConnected ? 'text-emerald-400' : 'text-rose-400'}`}>
                {isConnected ? 'Connected' : 'Not connected'}
              </span>
            </div>
          </div>
        </div>

        {health?.error && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block mb-0.5">Provider Diagnostic Message:</span>
              <span className="font-mono text-[11px] break-all">{health.error}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
