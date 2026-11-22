import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Loader2, ArrowRight, FileText, AlertCircle } from 'lucide-react';

/**
 * Reusable empty state for artifacts that haven't been generated yet for the current project.
 * Uses crisp bright styling with white surfaces, dark readable text, and professional blue accents.
 */
export default function EmptyArtifactState({
  title = "Artifact Not Generated Yet",
  description = "This artifact has not been synthesized for the current project.",
  icon: Icon = FileText,
  onGenerate,
  isGenerating = false,
  generateLabel = "Generate Artifact",
  hasRequirements = true,
}) {
  const navigate = useNavigate();

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-12 shadow-sm text-center max-w-2xl mx-auto space-y-6">
      <div className="w-16 h-16 rounded-2xl bg-blue-50 border border-blue-100 text-blue-600 flex items-center justify-center mx-auto shadow-sm">
        <Icon className="w-8 h-8" />
      </div>

      <div className="space-y-2">
        <h3 className="text-xl font-serif font-bold text-slate-900 tracking-tight">
          {title}
        </h3>
        <p className="text-xs sm:text-sm text-slate-600 leading-relaxed max-w-md mx-auto">
          {description}
        </p>
      </div>

      {!hasRequirements && (
        <div className="flex items-center gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-4 py-2.5 max-w-md mx-auto text-left">
          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>
            No requirements have been extracted for this project yet. Upload a requirement specification to extract specifications before generating engineering artifacts.
          </span>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
        {onGenerate && (
          <button
            onClick={onGenerate}
            disabled={isGenerating}
            className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold tracking-wide shadow-sm shadow-blue-500/20 disabled:opacity-50 transition-all flex items-center gap-2 cursor-pointer"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-white" />
                <span>Generating Artifact...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-blue-200" />
                <span>{generateLabel}</span>
              </>
            )}
          </button>
        )}

        {!hasRequirements ? (
          <button
            onClick={() => navigate('/requirements')}
            className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium border border-slate-200 flex items-center gap-1.5 transition-colors"
          >
            <span>Go to Requirements</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        ) : (
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium border border-slate-200 flex items-center gap-1.5 transition-colors"
          >
            <span>Back to Dashboard</span>
          </button>
        )}
      </div>
    </div>
  );
}
