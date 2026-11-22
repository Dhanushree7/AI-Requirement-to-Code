import React, { useState } from 'react';
import { Key, Eye, EyeOff, CheckCircle2, AlertCircle, Loader2, X, Shield } from 'lucide-react';
import { projectApi } from '../api';

const DEFAULT_MODELS = {
  gemini: 'gemini-1.5-pro',
  openai: 'gpt-4o',
  anthropic: 'claude-3-5-sonnet-20241022',
};

export default function ApiKeyModal({ isOpen, onClose, onSuccess, initialProvider = 'gemini' }) {
  const [provider, setProvider] = useState(initialProvider);
  const [model, setModel] = useState(DEFAULT_MODELS[initialProvider] || 'gemini-1.5-pro');
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  if (!isOpen) return null;

  const handleProviderChange = (e) => {
    const p = e.target.value;
    setProvider(p);
    setModel(DEFAULT_MODELS[p] || '');
    setError(null);
  };

  const handleTestAndSave = async (e) => {
    e.preventDefault();
    if (!apiKey.trim()) {
      setError("Please enter an API key.");
      return;
    }
    setTesting(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const res = await projectApi.testAndSaveProvider({
        provider,
        model,
        api_key: apiKey.trim(),
      });
      setSuccessMsg(res.message || "Connected successfully!");
      setTimeout(() => {
        if (onSuccess) onSuccess(res.status);
        if (onClose) onClose();
      }, 1000);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || "Connection test failed";
      setError(detail);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
      <div className="w-full max-w-md bg-[#111827] border border-orange-500/30 rounded-2xl p-6 shadow-2xl relative space-y-5 animate-in fade-in zoom-in duration-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center text-orange-400">
              <Key className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Connect AI Provider</h2>
              <p className="text-xs text-slate-400">Configure your LLM key for artifact generation</p>
            </div>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <form onSubmit={handleTestAndSave} className="space-y-4">
          <div>
            <label className="text-xs font-mono text-slate-400 block mb-1">Provider</label>
            <select
              value={provider}
              onChange={handleProviderChange}
              className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-orange-500"
            >
              <option value="gemini">Google Gemini</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic Claude</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-mono text-slate-400 block mb-1">Model Name</label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              required
              className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 font-mono focus:outline-none focus:border-orange-500"
              placeholder="e.g. gemini-1.5-pro, gpt-4o, claude-3-5-sonnet"
            />
          </div>

          <div>
            <label className="text-xs font-mono text-slate-400 block mb-1">API Key</label>
            <div className="relative">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                required
                className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 font-mono focus:outline-none focus:border-orange-500"
                placeholder="Paste API key (encrypted at rest)..."
                autoComplete="new-password"
              />
            </div>
            <p className="text-[10px] text-slate-500 mt-1 flex items-center gap-1">
              <Shield className="w-3 h-3 text-emerald-400" />
              Stored encrypted at rest on backend only. Never sent to browser.
            </p>
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-400 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          <div className="pt-2 flex justify-end gap-2.5">
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white"
              >
                Cancel
              </button>
            )}
            <button
              type="submit"
              disabled={testing}
              className="px-4 py-2 rounded-xl bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-2 shadow-lg shadow-orange-500/20"
            >
              {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Key className="w-3.5 h-3.5" />}
              <span>{testing ? "Testing Connection..." : "Test & Save"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
