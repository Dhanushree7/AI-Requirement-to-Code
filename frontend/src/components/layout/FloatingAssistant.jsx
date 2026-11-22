import React, { useState, useEffect } from 'react';
import { Sparkles, X, Send, Bot, User, BookOpen, ChevronRight, CornerDownLeft } from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { projectApi } from '../../api';

export default function FloatingAssistant() {
  const { activeProjectId, isAssistantOpen, setIsAssistantOpen } = useProject();
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'assistant',
      text: 'Hello! I am your Project-Aware RAG Assistant. Ask me anything about your uploaded requirements, database schema, architecture decisions, or APIs.',
      citations: []
    }
  ]);
  const [inputQuestion, setInputQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestedQuestions, setSuggestedQuestions] = useState([
    "Explain my architecture.",
    "What are the non-functional requirements?",
    "What authentication method is required?"
  ]);

  useEffect(() => {
    if (activeProjectId) {
      projectApi.getSuggestedQuestions(activeProjectId)
        .then(qs => {
          if (qs && qs.length > 0) setSuggestedQuestions(qs.map(item => item.q));
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
        grounded: res.grounded
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: 'assistant',
          text: 'Sorry, I encountered an issue querying the project context. Please ensure the backend is running and requirements have been analyzed.',
          citations: []
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Floating Pill (Always visible when chat drawer is closed) */}
      {!isAssistantOpen && (
        <button
          onClick={() => setIsAssistantOpen(true)}
          className="fixed bottom-6 right-6 z-50 bg-white hover:bg-slate-50 border border-slate-200 shadow-xl rounded-full py-2.5 px-4 flex items-center gap-3 transition-all duration-200 group hover:shadow-blue-500/10 cursor-pointer"
        >
          {/* Glowing Green Dot */}
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
          <span className="text-sm font-semibold text-slate-800 group-hover:text-blue-600">
            AI Query Assistant
          </span>
          <span className="text-[10px] font-mono uppercase bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full border border-blue-200">
            project-aware
          </span>
        </button>
      )}

      {/* Slide-over Chat Panel */}
      {isAssistantOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-[420px] max-w-[calc(100vw-3rem)] h-[580px] bg-white border border-slate-200 rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-200">
          {/* Drawer Header */}
          <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 border border-blue-200 flex items-center justify-center shadow-xs">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <div className="font-semibold text-sm text-slate-900">AI Query Assistant</div>
                <div className="text-[11px] text-teal-700 font-mono flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  Grounded in Project Context & Graph
                </div>
              </div>
            </div>
            <button
              onClick={() => setIsAssistantOpen(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 text-sm bg-white">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex gap-3 ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.sender === 'assistant' && (
                  <div className="w-7 h-7 rounded-lg bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center shrink-0 mt-0.5 shadow-xs">
                    <Bot className="w-4 h-4" />
                  </div>
                )}
                <div className={`max-w-[85%] rounded-xl p-3.5 space-y-2 ${
                  m.sender === 'user' 
                    ? 'bg-blue-600 !text-white rounded-br-none shadow-sm' 
                    : 'bg-slate-50 border border-slate-200 text-slate-800 rounded-bl-none shadow-xs'
                }`}>
                  <p className="leading-relaxed text-xs sm:text-sm whitespace-pre-wrap">{m.text}</p>
                  
                  {/* Source Citations */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="pt-2 border-t border-slate-200 mt-2 space-y-1">
                      <div className="text-[10px] font-mono uppercase text-teal-700 tracking-wider flex items-center gap-1 font-semibold">
                        <BookOpen className="w-3 h-3 text-teal-600" /> Source Citations
                      </div>
                      {m.citations.map((c, i) => (
                        <div key={i} className="text-[11px] bg-white rounded px-2 py-1 text-slate-700 border border-slate-200">
                          <span className="font-semibold text-teal-700">{c.source}:</span> {c.snippet}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {m.sender === 'user' && (
                  <div className="w-7 h-7 rounded-lg bg-blue-100 text-blue-700 border border-blue-200 flex items-center justify-center shrink-0 mt-0.5 font-semibold text-xs">
                    SE
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex gap-3 justify-start">
                <div className="w-7 h-7 rounded-lg bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 animate-spin" />
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-xl rounded-bl-none p-3 text-xs text-slate-600 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-bounce" />
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-bounce [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-bounce [animation-delay:0.4s]" />
                  Retrieving context & reasoning...
                </div>
              </div>
            )}
          </div>

          {/* Suggested Prompts */}
          {messages.length <= 2 && (
            <div className="px-4 pb-2 bg-white">
              <div className="text-[10px] font-mono uppercase text-slate-400 mb-1.5 font-semibold">Suggested Queries</div>
              <div className="flex flex-wrap gap-1.5">
                {suggestedQuestions.map((sq, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(sq)}
                    className="text-[11px] bg-slate-50 hover:bg-blue-50 border border-slate-200 hover:border-blue-300 rounded-lg px-2.5 py-1 text-slate-700 hover:text-blue-700 transition-colors truncate max-w-full text-left font-medium"
                  >
                    {sq}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input Box */}
          <div className="p-3 bg-slate-50 border-t border-slate-200">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex items-center gap-2 bg-white border border-slate-300 rounded-xl px-3 py-1.5 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition-all shadow-xs"
            >
              <input
                type="text"
                placeholder="Ask about your requirements or design..."
                value={inputQuestion}
                onChange={(e) => setInputQuestion(e.target.value)}
                className="flex-1 bg-transparent border-none text-xs text-slate-900 placeholder-slate-400 focus:outline-none"
              />
              <button
                type="submit"
                disabled={!inputQuestion.trim() || loading}
                className="p-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-40 !text-white transition-colors cursor-pointer"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
