import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("React Component Crash captured by ErrorBoundary:", error, errorInfo);
    this.setState({ errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#0B0F17] text-slate-100 flex items-center justify-center p-6">
          <div className="max-w-xl w-full p-6 rounded-2xl bg-[#111827] border border-red-500/30 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3 text-red-400">
              <AlertTriangle className="w-6 h-6 flex-shrink-0" />
              <h2 className="text-lg font-semibold tracking-tight">Something went wrong</h2>
            </div>
            <p className="text-sm text-slate-300">
              An unexpected rendering error occurred. The application caught this error instead of showing a blank screen:
            </p>
            <div className="p-4 rounded-xl bg-black/60 border border-slate-800 font-mono text-xs text-red-300 overflow-x-auto whitespace-pre-wrap">
              {this.state.error?.toString()}
            </div>
            {this.state.errorInfo?.componentStack && (
              <details className="text-xs text-slate-400">
                <summary className="cursor-pointer hover:text-slate-200">View component stack trace</summary>
                <pre className="mt-2 p-3 bg-black/40 rounded-lg overflow-x-auto font-mono text-[11px] text-slate-400">
                  {this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}
            <button
              onClick={() => window.location.reload()}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold transition-all"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Reload Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
