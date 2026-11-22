import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  Send, 
  Bot, 
  User, 
  BookOpen, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  HelpCircle,
  ShieldCheck
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { projectApi } from '../api';
import MarkdownViewer from '../components/MarkdownViewer';

export default function AssistantPage() {
  const { activeProjectId } = useProject();
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'assistant',
      text: 'Welcome to the Project-Aware Query Support Assistant. I have indexed your requirement document, generated architecture, database schema, APIs, test suite, and knowledge graph. Ask me any design or implementation question!',
      citations: []
    }
  ]);
  const [inputQuestion, setInputQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [sampleQuestions, setSampleQuestions] = useState([
    { label: "Architecture Explanation", q: "Explain my architecture." },
    { label: "Non-Functional Specs", q: "What are the non-functional requirements?" },
    { label: "Authentication Details", q: "What authentication method is required?" }
  ]);

  useEffect(() => {
    if (activeProjectId) {
      projectApi.getSuggestedQuestions(activeProjectId)
        .then(qs => {
          if (qs && qs.length > 0) setSampleQuestions(qs);
        })
        .catch(() => {});
    }
  }, [activeProjectId]);

  const handleSend = async (qText) => {
    const question = qText || inputQuestion;
    if (!question.trim() || loading || !activeProjectId) return;

    const userMsg = { id: Date.now().toString(), sender: 'user', text: question };
    setMessages(prev => [...prev, userMsg]);
    setInputQuestion('');
    setLoading(true);

    try {
      const res = await projectApi.queryRag(activeProjectId, question);
      const assistantMsg = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: res.answer,
        citations: res.citations || [],
        grounded: res.grounded,
        confidence: res.confidence
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: 'assistant',
          text: 'Unable to retrieve context for this question. Please ensure requirements have been extracted for this project.',
          citations: []
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-0.5 rounded text-[10px] font-mono uppercase bg-blue-50 text-blue-700 border border-blue-200 font-semibold">
            AI Query Support Assistant &bull; Project Grounded
          </span>
          <span className="text-xs font-mono text-slate-500">
            Vector Retrieval &bull; Project Context
          </span>
        </div>
        <h1 className="text-3xl font-serif font-bold text-slate-900 tracking-tight mt-1">
          AI Query Support Assistant
        </h1>
        <p className="text-sm text-slate-600 mt-1">
          Context-restricted assistant with source citations across document text, generated artifacts, and graph links.
        </p>
      </div>

      {/* Suggested Questions Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {sampleQuestions.map((sq, i) => (
          <button
            key={i}
            onClick={() => handleSend(sq.q)}
            className="p-3 bg-white hover:bg-blue-50/50 border border-slate-200 hover:border-blue-300 rounded-xl text-left transition-all group shadow-xs cursor-pointer"
          >
            <div className="text-[10px] font-mono uppercase text-blue-600 font-semibold group-hover:text-blue-700">
              {sq.label}
            </div>
            <div className="text-xs font-medium text-slate-800 mt-1 line-clamp-1">
              "{sq.q}"
            </div>
          </button>
        ))}
      </div>

      {/* Chat Window Card */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm flex flex-col h-[580px] overflow-hidden">
        {/* Messages Scroll Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 bg-white">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex gap-3.5 ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {m.sender === 'assistant' && (
                <div className="w-8 h-8 rounded-xl bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center shrink-0 mt-0.5 shadow-xs">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div className={`max-w-[80%] rounded-2xl p-4 space-y-3 ${
                m.sender === 'user' 
                  ? 'bg-blue-600 !text-white rounded-br-none shadow-sm' 
                  : 'bg-slate-50 border border-slate-200 text-slate-800 rounded-bl-none shadow-xs'
              }`}>
                {m.sender === 'assistant' ? (
                  <div className="prose prose-sm max-w-none text-slate-800">
                    <MarkdownViewer content={m.text} />
                  </div>
                ) : (
                  <p className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap !text-white">{m.text}</p>
                )}

                {/* Grounding & Citations */}
                {m.citations && m.citations.length > 0 && (
                  <div className="pt-3 border-t border-slate-200 mt-3 space-y-2">
                    <div className="text-[10px] font-mono uppercase text-teal-700 tracking-wider flex items-center gap-1 font-semibold">
                      <ShieldCheck className="w-3.5 h-3.5" /> Grounded Source Citations ({m.citations.length})
                    </div>
                    <div className="space-y-1.5">
                      {m.citations.map((c, i) => (
                        <div key={i} className="text-xs bg-white rounded-lg p-2.5 text-slate-700 border border-slate-200 shadow-xs">
                          <span className="font-semibold text-teal-700 font-mono">[{c.source}]</span>{' '}
                          <span className="text-slate-600">{c.snippet}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {m.sender === 'user' && (
                <div className="w-8 h-8 rounded-xl bg-blue-100 text-blue-700 border border-blue-200 font-bold text-xs flex items-center justify-center shrink-0 mt-0.5 shadow-xs">
                  SE
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-xl bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center shrink-0">
                <Loader2 className="w-4 h-4 animate-spin" />
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-2xl rounded-bl-none p-4 text-xs text-slate-600 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping" />
                <span>Searching vector store & reasoning over project artifacts...</span>
              </div>
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="p-4 bg-slate-50 border-t border-slate-200">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-3 bg-white border border-slate-300 rounded-xl px-4 py-2 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition-all shadow-xs"
          >
            <input
              type="text"
              placeholder="Ask a question about requirements, database schema, architecture, or APIs..."
              value={inputQuestion}
              onChange={(e) => setInputQuestion(e.target.value)}
              className="flex-1 bg-transparent border-none text-xs sm:text-sm text-slate-900 placeholder-slate-400 focus:outline-none"
            />
            <button
              type="submit"
              disabled={!inputQuestion.trim() || loading}
              className="p-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-40 !text-white transition-colors cursor-pointer"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
