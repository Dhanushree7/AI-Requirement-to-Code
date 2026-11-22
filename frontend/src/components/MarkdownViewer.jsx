import React from 'react';
import ReactMarkdown from 'react-markdown';

/**
 * Pre-processes markdown to heal broken table rows and split into
 * structured markdown blocks and table blocks.
 */
function parseMarkdownBlocks(text) {
  if (!text) return [];

  // Step 1: Heal table rows where cells were broken across multiple lines
  const rawLines = text.split(/\r?\n/);
  const healedLines = [];
  let inTable = false;

  for (let i = 0; i < rawLines.length; i++) {
    const line = rawLines[i];
    const trimmed = line.trim();

    if (trimmed.startsWith('|')) {
      inTable = true;
      healedLines.push(trimmed);
    } else if (inTable) {
      if (trimmed === '' || trimmed.startsWith('#')) {
        inTable = false;
        healedLines.push(line);
      } else {
        // Table cell continuation on a new line: merge into preceding row
        if (healedLines.length > 0) {
          let prev = healedLines[healedLines.length - 1];
          if (prev.endsWith('|')) {
            prev = prev.slice(0, -1).trimEnd() + ' ' + trimmed + ' |';
          } else {
            prev = prev + ' ' + trimmed;
          }
          healedLines[healedLines.length - 1] = prev;
        } else {
          healedLines.push(line);
        }
      }
    } else {
      healedLines.push(line);
    }
  }

  // Step 2: Separate markdown text from table blocks
  const blocks = [];
  let currentMarkdown = [];
  let currentTable = null;

  function flushMarkdown() {
    if (currentMarkdown.length > 0) {
      const content = currentMarkdown.join('\n').trim();
      if (content) {
        blocks.push({ type: 'markdown', content });
      }
      currentMarkdown = [];
    }
  }

  function flushTable() {
    if (currentTable) {
      blocks.push(currentTable);
      currentTable = null;
    }
  }

  function isSeparatorRow(line) {
    const trimmed = line.trim();
    if (!trimmed.startsWith('|') || !trimmed.endsWith('|')) return false;
    const parts = trimmed.slice(1, -1).split('|');
    return parts.length > 0 && parts.every(p => /^[\s:-]+$/.test(p) && p.includes('-'));
  }

  function parseRow(line) {
    const trimmed = line.trim();
    const inner = trimmed.startsWith('|') && trimmed.endsWith('|')
      ? trimmed.slice(1, -1)
      : trimmed;
    return inner.split('|').map(c => c.trim());
  }

  let idx = 0;
  while (idx < healedLines.length) {
    const line = healedLines[idx];
    const nextLine = idx + 1 < healedLines.length ? healedLines[idx + 1] : null;

    // Check for table start: header row followed by separator row
    if (!currentTable && line.trim().startsWith('|') && nextLine && isSeparatorRow(nextLine)) {
      flushMarkdown();
      const headers = parseRow(line);
      const sepParts = parseRow(nextLine);
      const alignments = sepParts.map(p => {
        const left = p.trim().startsWith(':');
        const right = p.trim().endsWith(':');
        if (left && right) return 'center';
        if (right) return 'right';
        return 'left';
      });

      currentTable = {
        type: 'table',
        headers,
        alignments,
        rows: []
      };
      idx += 2;
      continue;
    }

    if (currentTable) {
      if (line.trim().startsWith('|')) {
        const cells = parseRow(line);
        while (cells.length < currentTable.headers.length) cells.push('');
        currentTable.rows.push(cells.slice(0, currentTable.headers.length));
        idx++;
        continue;
      } else if (line.trim() === '') {
        flushTable();
        idx++;
        continue;
      } else {
        flushTable();
        currentMarkdown.push(line);
        idx++;
        continue;
      }
    }

    currentMarkdown.push(line);
    idx++;
  }

  flushTable();
  flushMarkdown();
  return blocks;
}

/**
 * Inline cell renderer parsing bold, italics, code, and links without paragraph margins.
 */
function InlineCell({ content }) {
  if (!content) return null;
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <span className="inline-block">{children}</span>,
        strong: ({ children }) => <strong className="font-semibold text-slate-900 dark:text-white">{children}</strong>,
        code: ({ children }) => (
          <code className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-blue-700 dark:text-blue-400 font-mono text-[11px] border border-slate-200 dark:border-slate-700">
            {children}
          </code>
        ),
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 underline underline-offset-2">
            {children}
          </a>
        )
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

/**
 * High-fidelity responsive Markdown table component.
 */
function MarkdownTable({ table }) {
  const { headers, alignments, rows } = table;

  return (
    <div className="overflow-x-auto my-4 rounded-xl border border-slate-200 dark:border-slate-700/80 bg-white dark:bg-[#0f172a] shadow-xs">
      <table className="w-full text-left text-xs border-collapse">
        <thead className="bg-slate-50 dark:bg-slate-800/90 text-slate-700 dark:text-slate-200 font-mono text-[11px] uppercase tracking-wider border-b border-slate-200 dark:border-slate-700">
          <tr>
            {headers.map((h, i) => {
              const align = alignments[i] || 'left';
              const alignClass = align === 'center' ? 'text-center' : align === 'right' ? 'text-right' : 'text-left';
              return (
                <th
                  key={i}
                  className={`px-4 py-3 font-semibold text-slate-800 dark:text-slate-100 ${alignClass} ${i === 0 ? 'whitespace-nowrap' : ''}`}
                >
                  <InlineCell content={h} />
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
          {rows.map((row, rIdx) => (
            <tr
              key={rIdx}
              className={`transition-colors hover:bg-slate-50/80 dark:hover:bg-slate-800/50 ${
                rIdx % 2 === 1 ? 'bg-slate-50/40 dark:bg-slate-900/40' : 'bg-transparent'
              }`}
            >
              {row.map((cell, cIdx) => {
                const align = alignments[cIdx] || 'left';
                const alignClass = align === 'center' ? 'text-center' : align === 'right' ? 'text-right' : 'text-left';
                return (
                  <td
                    key={cIdx}
                    className={`px-4 py-2.5 font-sans leading-relaxed ${alignClass} ${cIdx === 0 ? 'font-mono text-[11px] font-medium text-slate-900 dark:text-slate-100 whitespace-nowrap' : ''}`}
                  >
                    <InlineCell content={cell} />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Clean, professional Markdown renderer supporting headings, styled tables, lists, and code blocks.
 */
export default function MarkdownViewer({ content, className = '' }) {
  if (!content) return null;

  const blocks = parseMarkdownBlocks(content);

  const sharedComponents = {
    h1: ({ node, ...props }) => (
      <h1 className="text-xl font-bold text-slate-900 dark:text-white mt-5 mb-2.5 pb-1.5 border-b border-slate-200 dark:border-slate-700 tracking-tight" {...props} />
    ),
    h2: ({ node, ...props }) => (
      <h2 className="text-base font-semibold text-slate-900 dark:text-white mt-4 mb-2 tracking-tight flex items-center gap-2" {...props} />
    ),
    h3: ({ node, ...props }) => (
      <h3 className="text-sm font-semibold text-blue-700 dark:text-blue-400 mt-3.5 mb-1.5" {...props} />
    ),
    h4: ({ node, ...props }) => (
      <h4 className="text-xs font-semibold uppercase font-mono tracking-wider text-slate-800 dark:text-slate-300 mt-3 mb-1" {...props} />
    ),
    p: ({ node, ...props }) => (
      <p className="text-xs sm:text-sm text-slate-700 dark:text-slate-300 leading-relaxed mb-3 last:mb-0" {...props} />
    ),
    ul: ({ node, ...props }) => (
      <ul className="list-disc list-outside text-xs sm:text-sm text-slate-700 dark:text-slate-300 space-y-1.5 my-2.5 pl-5" {...props} />
    ),
    ol: ({ node, ...props }) => (
      <ol className="list-decimal list-outside text-xs sm:text-sm text-slate-700 dark:text-slate-300 space-y-1.5 my-2.5 pl-5" {...props} />
    ),
    li: ({ node, ...props }) => (
      <li className="leading-relaxed pl-1" {...props} />
    ),
    blockquote: ({ node, ...props }) => (
      <blockquote className="border-l-2 border-blue-600 pl-3.5 py-1.5 my-2.5 bg-blue-50/50 dark:bg-slate-800/60 text-slate-700 dark:text-slate-300 italic text-xs sm:text-sm rounded-r-lg" {...props} />
    ),
    code: ({ node, inline, className, children, ...props }) => {
      if (inline) {
        return (
          <code className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-blue-700 dark:text-blue-400 font-mono text-[11px] border border-slate-200 dark:border-slate-700" {...props}>
            {children}
          </code>
        );
      }
      return (
        <pre className="bg-slate-50 dark:bg-[#0c1222] border border-slate-200 dark:border-slate-800 rounded-xl p-3.5 text-xs text-slate-800 dark:text-slate-200 font-mono overflow-x-auto my-2.5 leading-relaxed">
          <code {...props}>{children}</code>
        </pre>
      );
    },
    hr: ({ node, ...props }) => (
      <hr className="border-slate-200 dark:border-slate-800 my-4" {...props} />
    ),
    strong: ({ node, ...props }) => (
      <strong className="font-semibold text-slate-900 dark:text-white" {...props} />
    ),
    a: ({ node, ...props }) => (
      <a className="text-blue-600 dark:text-blue-400 hover:underline underline-offset-2 transition-colors font-medium" target="_blank" rel="noopener noreferrer" {...props} />
    )
  };

  return (
    <div className={`prose-light font-sans text-slate-800 dark:text-slate-200 ${className}`}>
      {blocks.map((block, i) => {
        if (block.type === 'table') {
          return <MarkdownTable key={i} table={block} />;
        }
        return (
          <ReactMarkdown key={i} components={sharedComponents}>
            {block.content}
          </ReactMarkdown>
        );
      })}
    </div>
  );
}
