import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Search, 
  Plus, 
  AlertTriangle, 
  CheckCircle2, 
  Edit3, 
  Trash2, 
  HelpCircle, 
  Filter, 
  Loader2, 
  Sparkles,
  ChevronDown
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { projectApi } from '../api';

export default function RequirementsPage() {
  const { activeProjectId } = useProject();
  const [requirements, setRequirements] = useState([]);
  const [domainModel, setDomainModel] = useState(null);
  const [showDomainReview, setShowDomainReview] = useState(false);
  const [domainEditingJson, setDomainEditingJson] = useState('');
  const [summary, setSummary] = useState(null);
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [expandedReq, setExpandedReq] = useState(null);

  // Modal state for Add/Edit
  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [formData, setFormData] = useState({
    req_id: '',
    category: 'functional',
    title: '',
    description: '',
    priority: 'medium',
    module_name: ''
  });

  const loadRequirements = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      const sum = await projectApi.getRequirementsSummary(activeProjectId);
      setSummary(sum);
      setRequirements(sum.requirements || []);

      const dm = await projectApi.getDomainModel(activeProjectId);
      setDomainModel(dm && Object.keys(dm).length > 0 ? dm : null);
      setDomainEditingJson(dm && Object.keys(dm).length > 0 ? JSON.stringify(dm, null, 2) : '');
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRequirements();
  }, [activeProjectId]);

  const handleReanalyze = async () => {
    if (!activeProjectId || analyzing) return;
    setAnalyzing(true);
    try {
      await projectApi.analyzeRequirements(activeProjectId);
      await loadRequirements();
    } catch (err) {
      console.error(err);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Are you sure you want to delete this requirement?")) return;
    try {
      await projectApi.deleteRequirement(id);
      await loadRequirements();
    } catch (err) {
      console.error(err);
    }
  };

  const handleOpenAddModal = () => {
    setEditingItem(null);
    setFormData({
      req_id: `FR-${String(requirements.length + 1).padStart(3, '0')}`,
      category: 'functional',
      title: '',
      description: '',
      priority: 'medium',
      module_name: ''
    });
    setModalOpen(true);
  };

  const handleOpenEditModal = (item) => {
    setEditingItem(item);
    setFormData({
      req_id: item.req_id,
      category: item.category,
      title: item.title,
      description: item.description,
      priority: item.priority,
      module_name: item.module_name || ''
    });
    setModalOpen(true);
  };

  const handleSaveModal = async (e) => {
    e.preventDefault();
    try {
      if (editingItem) {
        await projectApi.updateRequirement(editingItem.id, formData);
      } else {
        await projectApi.createRequirement(activeProjectId, formData);
      }
      setModalOpen(false);
      await loadRequirements();
    } catch (err) {
      console.error(err);
    }
  };

  const tabs = [
    { id: 'all', label: 'All', count: summary?.total || 0 },
    { id: 'functional', label: 'Functional (FR)', count: summary?.functional_count || 0 },
    { id: 'non_functional', label: 'Non-Functional (NFR)', count: summary?.non_functional_count || 0 },
    { id: 'actor', label: 'Actors', count: summary?.actor_count || 0 },
    { id: 'entity', label: 'Entities', count: summary?.entity_count || 0 },
    { id: 'module', label: 'Modules', count: summary?.module_count || 0 },
    { id: 'constraint', label: 'Constraints', count: summary?.constraint_count || 0 },
  ];

  const filteredRequirements = requirements.filter(r => {
    const matchesTab = activeTab === 'all' || r.category === activeTab;
    const matchesSearch = !searchQuery.trim() || 
      r.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.req_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTab && matchesSearch;
  });

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-bold text-white tracking-tight">
            Software Requirements Specification
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Structured functional and non-functional requirements extracted and verified from uploaded document.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowDomainReview(!showDomainReview)}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-medium border border-teal-500/30 bg-teal-500/10 text-teal-400 hover:bg-teal-500/20 transition-all"
            title="Review and edit the full Domain Model before code generation"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {showDomainReview ? 'Hide Domain Model' : 'Review Domain Model'}
          </button>
          <button
            onClick={handleReanalyze}
            disabled={analyzing}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-2 border border-slate-700 disabled:opacity-50"
          >
            {analyzing ? <Loader2 className="w-3.5 h-3.5 animate-spin text-orange-400" /> : <Sparkles className="w-3.5 h-3.5 text-orange-400" />}
            <span>Re-analyze</span>
          </button>
          <button
            onClick={handleOpenAddModal}
            className="px-4 py-2 rounded-xl bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold flex items-center gap-2 shadow-lg shadow-orange-500/20"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Requirement</span>
          </button>
        </div>
      </div>

      {/* Domain Model Review / Edit Screen */}
      {showDomainReview && (
        <div className="p-5 rounded-2xl bg-[#111827] border border-teal-500/30 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-teal-400" />
                Validated Domain Model (Entities, Attributes, Business Rules, State Workflows)
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Review or edit the unified model before deep code generation. Saving synchronizes the Knowledge Graph & RAG index.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={async () => {
                  try {
                    const parsed = JSON.parse(domainEditingJson);
                    await projectApi.updateDomainModel(activeProjectId, parsed);
                    setDomainModel(parsed);
                    alert("Domain Model updated! Knowledge Graph and RAG index re-synchronized.");
                  } catch (e) {
                    alert("Invalid JSON: " + e.message);
                  }
                }}
                className="px-3.5 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold"
              >
                Save & Synchronize
              </button>
              <button
                onClick={() => setShowDomainReview(false)}
                className="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white text-xs"
              >
                Close
              </button>
            </div>
          </div>

          <textarea
            value={domainEditingJson}
            onChange={(e) => setDomainEditingJson(e.target.value)}
            rows={14}
            className="w-full font-mono text-xs bg-[#090D16] border border-slate-800 rounded-xl p-3.5 text-slate-200 focus:outline-none focus:border-teal-500/50"
            placeholder="Domain Model JSON (summary, actors, entities, business rules, workflows)..."
          />
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 overflow-x-auto pb-1">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3.5 py-2 rounded-lg text-xs font-medium transition-colors flex items-center gap-2 whitespace-nowrap ${
              activeTab === tab.id
                ? 'bg-slate-800 text-white font-semibold border-b-2 border-orange-500 rounded-b-none'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <span>{tab.label}</span>
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono ${
              activeTab === tab.id ? 'bg-orange-500/20 text-orange-300' : 'bg-slate-900 text-slate-500'
            }`}>
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Search Bar & Filter Stats */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by ID, title, or keywords..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#131B2E] border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-orange-500"
          />
        </div>

        {summary?.ambiguous_count > 0 && (
          <div className="flex items-center gap-2 text-xs font-mono text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-xl px-3 py-1.5">
            <AlertTriangle className="w-4 h-4" />
            <span>{summary.ambiguous_count} ambiguous specifications require developer clarification</span>
          </div>
        )}
      </div>

      {/* Requirements Table */}
      <div className="bg-[#131B2E] border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        {loading ? (
          <div className="p-12 text-center text-slate-400 text-sm flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-orange-400" />
            <span>Loading requirements...</span>
          </div>
        ) : filteredRequirements.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-sm">
            No requirements match your current filter.
          </div>
        ) : (
          <div className="divide-y divide-slate-800/80">
            {filteredRequirements.map((req) => {
              const isExpanded = expandedReq === req.id;
              const hasQuestions = req.clarifying_questions && req.clarifying_questions.length > 0;

              return (
                <div key={req.id} className="p-4 hover:bg-[#162138] transition-colors group">
                  <div className="flex items-start justify-between gap-4">
                    {/* Left: ID & Title & Description */}
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2.5">
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-orange-500/15 text-orange-400 border border-orange-500/30">
                          {req.req_id}
                        </span>
                        <h3 className="text-sm font-semibold text-slate-100">
                          {req.title}
                        </h3>
                        {req.module_name && (
                          <span className="text-[11px] font-mono text-slate-500 bg-slate-900 px-2 py-0.5 rounded">
                            {req.module_name}
                          </span>
                        )}
                        {req.priority && (
                          <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded ${
                            req.priority === 'high' 
                              ? 'bg-red-500/10 text-red-400 border border-red-500/20' 
                              : 'bg-slate-800 text-slate-400'
                          }`}>
                            {req.priority}
                          </span>
                        )}
                        {req.is_ambiguous && (
                          <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" /> Ambiguous
                          </span>
                        )}
                      </div>

                      <p className="text-xs text-slate-300 leading-relaxed pl-0.5">
                        {req.description}
                      </p>

                      {/* Clarifying Questions Accordion */}
                      {req.is_ambiguous && hasQuestions && (
                        <div className="mt-2 pl-0.5">
                          <button
                            onClick={() => setExpandedReq(isExpanded ? null : req.id)}
                            className="text-[11px] text-amber-400 hover:text-amber-300 flex items-center gap-1 font-mono"
                          >
                            <HelpCircle className="w-3 h-3" />
                            <span>{req.clarifying_questions.length} Suggested Clarifying Questions</span>
                            <ChevronDown className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                          </button>
                          
                          {isExpanded && (
                            <div className="mt-2 p-3 bg-amber-500/5 border border-amber-500/20 rounded-xl space-y-1.5 animate-in fade-in duration-150">
                              <div className="text-[11px] font-medium text-amber-300">
                                Ambiguity Note: {req.ambiguity_notes}
                              </div>
                              <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
                                {req.clarifying_questions.map((q, qIdx) => (
                                  <li key={qIdx}>{q}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Right: Row Actions */}
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handleOpenEditModal(req)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                        title="Edit Requirement"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDelete(req.id)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                        title="Delete Requirement"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Add / Edit Requirement Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#111726] border border-slate-700 rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-4">
            <h3 className="text-base font-serif font-bold text-white">
              {editingItem ? 'Edit Requirement' : 'Add New Requirement'}
            </h3>
            <form onSubmit={handleSaveModal} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-mono text-slate-400">Requirement ID</label>
                  <input
                    type="text"
                    value={formData.req_id}
                    onChange={e => setFormData({ ...formData, req_id: e.target.value })}
                    required
                    className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                  />
                </div>
                <div>
                  <label className="text-xs font-mono text-slate-400">Category</label>
                  <select
                    value={formData.category}
                    onChange={e => setFormData({ ...formData, category: e.target.value })}
                    className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                  >
                    <option value="functional">Functional</option>
                    <option value="non_functional">Non-Functional</option>
                    <option value="actor">Actor</option>
                    <option value="entity">Entity</option>
                    <option value="module">Module</option>
                    <option value="constraint">Constraint</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-mono text-slate-400">Title</label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={e => setFormData({ ...formData, title: e.target.value })}
                  required
                  placeholder="e.g. Catalog Search with Filter by Subject"
                  className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                />
              </div>

              <div>
                <label className="text-xs font-mono text-slate-400">Description</label>
                <textarea
                  rows={3}
                  value={formData.description}
                  onChange={e => setFormData({ ...formData, description: e.target.value })}
                  required
                  placeholder="Detailed functional specification..."
                  className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-mono text-slate-400">Module</label>
                  <input
                    type="text"
                    value={formData.module_name}
                    onChange={e => setFormData({ ...formData, module_name: e.target.value })}
                    placeholder="e.g. Catalog Management"
                    className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                  />
                </div>
                <div>
                  <label className="text-xs font-mono text-slate-400">Priority</label>
                  <select
                    value={formData.priority}
                    onChange={e => setFormData({ ...formData, priority: e.target.value })}
                    className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                  >
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold"
                >
                  Save Requirement
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
