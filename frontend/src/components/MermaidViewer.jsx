import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  // Enforce strict security: encodes HTML entities in labels and disables script/click execution
  securityLevel: 'strict',
  themeVariables: {
    darkMode: true,
    background: '#131B2E',
    primaryColor: '#1E293B',
    primaryTextColor: '#F8FAFC',
    primaryBorderColor: '#334155',
    lineColor: '#14B8A6',
    secondaryColor: '#0F172A',
    tertiaryColor: '#1E293B',
  }
});

export default function MermaidViewer({ chart, id = 'mermaid-diagram' }) {
  const containerRef = useRef(null);
  const [svgContent, setSvgContent] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!chart || !containerRef.current) return;
    const renderChart = async () => {
      try {
        setError(null);
        const uniqueId = `${id}-${Math.random().toString(36).substring(2, 9)}`;
        const { svg } = await mermaid.render(uniqueId, chart);
        setSvgContent(svg);
      } catch (err) {
        console.error("Mermaid render error:", err);
        setError("Could not render diagram syntax.");
      }
    };
    renderChart();
  }, [chart, id]);

  if (error) {
    return (
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl text-xs font-mono text-slate-400 overflow-x-auto whitespace-pre">
        {chart}
      </div>
    );
  }

  return (
    <div 
      ref={containerRef}
      className="w-full overflow-x-auto p-4 flex justify-center items-center select-none"
      dangerouslySetInnerHTML={{ __html: svgContent }}
    />
  );
}
