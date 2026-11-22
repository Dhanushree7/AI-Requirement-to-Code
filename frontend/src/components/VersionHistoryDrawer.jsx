import React from 'react';
import { History, RotateCcw, X, Clock } from 'lucide-react';

export default function VersionHistoryDrawer({
  isOpen,
  onClose,
  versions = [],
  currentVersion = 1,
  onRestore,
  artifactName = "Artifact"
}) {
  if (!isOpen) return null;

  return (
    <div className="bg-[#131B2E] border border-slate-700/80 rounded-2xl p-5 shadow-2xl space-y-3 animate-in fade-in duration-200">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-orange-400" />
          <h3 className="text-xs font-mono uppercase tracking-wider text-slate-200 font-bold">
            {artifactName} Version History
          </h3>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {versions.length === 0 ? (
        <div className="py-4 text-center text-xs text-slate-400 font-mono">
          No prior revisions recorded. Current version is v{currentVersion}.
        </div>
      ) : (
        <div className="divide-y divide-slate-800/80 max-h-60 overflow-y-auto pr-1">
          {versions.map((v) => (
            <div key={v.id || v.version_number} className="py-3 flex items-center justify-between text-xs">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className={`font-mono font-bold px-1.5 py-0.5 rounded text-[11px] ${v.version_number === currentVersion ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-slate-800 text-slate-300'}`}>
                    v{v.version_number}
                  </span>
                  <span className="text-slate-300 font-medium">
                    {v.changelog || 'Automated generation'}
                  </span>
                </div>
                <div className="flex items-center gap-1 text-[11px] text-slate-500">
                  <Clock className="w-3 h-3" />
                  <span>{new Date(v.created_at).toLocaleString()}</span>
                </div>
              </div>

              {v.version_number !== currentVersion && (
                <button
                  onClick={() => onRestore(v.version_number)}
                  className="px-2.5 py-1 rounded-lg bg-teal-500/10 hover:bg-teal-500/20 text-teal-400 border border-teal-500/30 text-xs font-mono flex items-center gap-1.5 transition-colors"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Restore</span>
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
