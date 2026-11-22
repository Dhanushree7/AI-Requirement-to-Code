import React, { useState, useEffect } from 'react';
import { 
  CheckSquare, 
  Download, 
  Plus, 
  Search, 
  Filter, 
  Edit3, 
  Trash2, 
  CheckCircle2, 
  AlertTriangle, 
  RefreshCw, 
  Loader2, 
  AlertCircle 
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { projectApi } from '../api';
import EmptyArtifactState from '../components/EmptyArtifactState';

const typeColors = {
  positive: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  negative: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
  boundary: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
};

export default function TestCasesPage() {
  const { activeProjectId } = useProject();
  const [artifact, setArtifact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('ALL');
  const [regenerating, setRegenerating] = useState(false);

  // Edit / Add Modal
  const [modalOpen, setModalOpen] = useState(false);
  const [editingIndex, setEditingIndex] = useState(null);
  const [formData, setFormData] = useState({
    test_id: '',
    linked_req_id: '',
    scenario: '',
    preconditions: '',
    steps: '',
    expected_result: '',
    type: 'positive'
  });

  const loadArtifact = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      const data = await projectApi.getArtifact(activeProjectId, 'testcases');
      setArtifact(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadArtifact();
  }, [activeProjectId]);

  const handleRegenerate = async () => {
    if (!activeProjectId || regenerating) return;
    setRegenerating(true);
    try {
      const updated = await projectApi.regenerateArtifact(activeProjectId, 'testcases', {});
      setArtifact(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setRegenerating(false);
    }
  };

  const extractCases = (data) => {
    if (!data) return [];
    if (Array.isArray(data.cases) && data.cases.length > 0) return data.cases;
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.test_cases)) return data.test_cases;
    if (Array.isArray(data.tests)) return data.tests;
    return [];
  };

  const cases = extractCases(artifact?.content);

  const filteredCases = cases.filter(c => {
    const matchesType = filterType === 'ALL' || c.type === filterType;
    const matchesSearch = !searchQuery.trim() ||
      c.test_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.linked_req_id && c.linked_req_id.toLowerCase().includes(searchQuery.toLowerCase())) ||
      c.scenario.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesType && matchesSearch;
  });

  const handleExportCsv = () => {
    let csv = 'Test ID,Linked Req,Type,Scenario,Preconditions,Steps,Expected Result\n';
    cases.forEach(c => {
      const safe = (str) => `"${(str || '').replace(/"/g, '""')}"`;
      csv += `${safe(c.test_id)},${safe(c.linked_req_id)},${safe(c.type)},${safe(c.scenario)},${safe(c.preconditions)},${safe(c.steps)},${safe(c.expected_result)}\n`;
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `test_cases_${activeProjectId.slice(0, 8)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleExportExcel = () => {
    let xml = '<?xml version="1.0"?><?mso-application progid="Excel.Sheet"?>\n';
    xml += '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">\n';
    xml += '  <Worksheet ss:Name="Test Cases">\n';
    xml += '    <Table>\n';
    xml += '      <Row>\n';
    ['Test ID', 'Linked Req', 'Type', 'Scenario', 'Preconditions', 'Steps', 'Expected Result'].forEach(h => {
      xml += `        <Cell><Data ss:Type="String">${h}</Data></Cell>\n`;
    });
    xml += '      </Row>\n';
    cases.forEach(c => {
      xml += '      <Row>\n';
      [c.test_id, c.linked_req_id, c.type, c.scenario, c.preconditions, c.steps, c.expected_result].forEach(val => {
        const escaped = (val || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        xml += `        <Cell><Data ss:Type="String">${escaped}</Data></Cell>\n`;
      });
      xml += '      </Row>\n';
    });
    xml += '    </Table>\n';
    xml += '  </Worksheet>\n';
    xml += '</Workbook>';

    const blob = new Blob([xml], { type: 'application/vnd.ms-excel;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `test_cases_${activeProjectId.slice(0, 8)}.xls`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleOpenAdd = () => {
    setEditingIndex(null);
    setFormData({
      test_id: `TC-${String(cases.length + 1).padStart(3, '0')}`,
      linked_req_id: '',
      scenario: '',
      preconditions: '',
      steps: '',
      expected_result: '',
      type: 'positive'
    });
    setModalOpen(true);
  };

  const handleOpenEdit = (c, index) => {
    setEditingIndex(index);
    setFormData({ ...c });
    setModalOpen(true);
  };

  const handleSaveModal = async (e) => {
    e.preventDefault();
    const newCases = [...cases];
    if (editingIndex !== null) {
      newCases[editingIndex] = formData;
    } else {
      newCases.push(formData);
    }

    try {
      const updated = await projectApi.updateArtifact(activeProjectId, 'testcases', {
        content: { ...artifact.content, cases: newCases },
        changelog: editingIndex !== null ? `Updated ${formData.test_id}` : `Added ${formData.test_id}`
      });
      setArtifact(updated);
      setModalOpen(false);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (index) => {
    if (!confirm("Are you sure you want to delete this test case?")) return;
    const newCases = cases.filter((_, i) => i !== index);
    try {
      const updated = await projectApi.updateArtifact(activeProjectId, 'testcases', {
        content: { ...artifact.content, cases: newCases },
        changelog: `Deleted test case`
      });
      setArtifact(updated);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Test Specification Suite
            </span>
            <span className="text-xs font-mono text-slate-400">
              {cases.length} Verified Scenarios
            </span>
          </div>
          <h1 className="text-3xl font-serif font-bold text-white tracking-tight mt-1">
            Requirement-Linked Test Cases
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Scenarios generated straight from requirements specifications, linking functional IDs to positive, negative, and boundary tests.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5 disabled:opacity-50"
          >
            {regenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin text-orange-400" /> : <RefreshCw className="w-3.5 h-3.5 text-orange-400" />}
            <span>Regenerate</span>
          </button>
          <button
            onClick={handleExportCsv}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5"
            title="Export as CSV"
          >
            <Download className="w-3.5 h-3.5 text-teal-400" />
            <span>Export CSV</span>
          </button>
          <button
            onClick={handleExportExcel}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5"
            title="Export as Excel"
          >
            <Download className="w-3.5 h-3.5 text-emerald-400" />
            <span>Export Excel</span>
          </button>
          <button
            onClick={handleOpenAdd}
            className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-emerald-600/20"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Test Case</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by test ID, requirement, or scenario..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#131B2E] border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-orange-500"
          />
        </div>

        <div className="flex items-center gap-2">
          {['ALL', 'positive', 'negative', 'boundary'].map(t => (
            <button
              key={t}
              onClick={() => setFilterType(t)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono uppercase transition-colors ${
                filterType === t 
                  ? 'bg-slate-800 text-white font-bold border border-slate-700' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Test Cases Table */}
      {loading ? (
        <div className="p-16 text-center text-slate-400 text-sm flex items-center justify-center gap-2 bg-[#131B2E] border border-slate-800 rounded-2xl">
          <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
          <span>Loading test suite...</span>
        </div>
      ) : (!artifact || cases.length === 0) ? (
        <EmptyArtifactState
          title="Test Cases Not Generated Yet"
          description="Synthesize requirement-grounded positive, negative, and boundary test scenarios with concrete execution steps and verification assertions."
          icon={CheckSquare}
          onGenerate={handleRegenerate}
          isGenerating={regenerating}
          generateLabel="Generate Test Cases"
        />
      ) : (
        <div className="bg-[#131B2E] border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
          {filteredCases.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-sm">
              No test cases found matching your filters.
            </div>
          ) : (
          <div className="divide-y divide-slate-800/80">
            {filteredCases.map((tc, idx) => {
              const badgeClass = typeColors[tc.type] || 'bg-slate-800 text-slate-400 border-slate-700';

              return (
                <div key={tc.test_id || idx} className="p-5 hover:bg-[#162138] transition-colors group space-y-3">
                  <div className="flex items-start justify-between gap-4">
                    {/* Top Row: Test ID & Req Link & Badges */}
                    <div className="flex items-center gap-2.5">
                      <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-slate-900 text-orange-400 border border-slate-800">
                        {tc.test_id}
                      </span>
                      {tc.linked_req_id && (
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono text-teal-400 bg-teal-500/10 border border-teal-500/20">
                          {tc.linked_req_id}
                        </span>
                      )}
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${badgeClass}`}>
                        {tc.type}
                      </span>
                    </div>

                    {/* Action buttons on hover */}
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handleOpenEdit(tc, idx)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                        title="Edit Scenario"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDelete(idx)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                        title="Delete Scenario"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Scenario Title */}
                  <h3 className="text-sm font-semibold text-slate-100">
                    {tc.scenario}
                  </h3>

                  {/* Preconditions, Steps, Expected Result Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1 text-xs">
                    <div className="p-3 bg-[#0E1424] rounded-xl border border-slate-800/80 space-y-1">
                      <div className="text-[10px] font-mono uppercase text-slate-400 font-semibold">Preconditions</div>
                      <p className="text-slate-300 text-xs">{tc.preconditions || 'None'}</p>
                    </div>

                    <div className="p-3 bg-[#0E1424] rounded-xl border border-slate-800/80 space-y-1">
                      <div className="text-[10px] font-mono uppercase text-slate-400 font-semibold">Test Execution Steps</div>
                      <p className="text-slate-300 text-xs whitespace-pre-line">{tc.steps}</p>
                    </div>

                    <div className="p-3 bg-[#0E1424] rounded-xl border border-slate-800/80 space-y-1">
                      <div className="text-[10px] font-mono uppercase text-teal-400 font-semibold">Expected Verification Result</div>
                      <p className="text-slate-200 text-xs">{tc.expected_result}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      )}

      {/* Modal for Add / Edit */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#111726] border border-slate-700 rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-4">
            <h3 className="text-base font-serif font-bold text-white">
              {editingIndex !== null ? 'Edit Test Case' : 'Add Test Case'}
            </h3>
            <form onSubmit={handleSaveModal} className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-mono text-slate-400">Test ID</label>
                  <input
                    type="text"
                    value={formData.test_id}
                    onChange={e => setFormData({ ...formData, test_id: e.target.value })}
                    required
                    className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                  />
                </div>
                <div>
                  <label className="text-xs font-mono text-slate-400">Linked Req ID</label>
                  <input
                    type="text"
                    value={formData.linked_req_id}
                    onChange={e => setFormData({ ...formData, linked_req_id: e.target.value })}
                    placeholder="e.g. FR-001"
                    className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                  />
                </div>
                <div>
                  <label className="text-xs font-mono text-slate-400">Type</label>
                  <select
                    value={formData.type}
                    onChange={e => setFormData({ ...formData, type: e.target.value })}
                    className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                  >
                    <option value="positive">Positive</option>
                    <option value="negative">Negative</option>
                    <option value="boundary">Boundary</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-mono text-slate-400">Scenario Description</label>
                <input
                  type="text"
                  value={formData.scenario}
                  onChange={e => setFormData({ ...formData, scenario: e.target.value })}
                  required
                  placeholder="e.g. Verify patron can search books by keyword"
                  className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                />
              </div>

              <div>
                <label className="text-xs font-mono text-slate-400">Preconditions</label>
                <input
                  type="text"
                  value={formData.preconditions}
                  onChange={e => setFormData({ ...formData, preconditions: e.target.value })}
                  placeholder="State prerequisites..."
                  className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                />
              </div>

              <div>
                <label className="text-xs font-mono text-slate-400">Execution Steps</label>
                <textarea
                  rows={2}
                  value={formData.steps}
                  onChange={e => setFormData({ ...formData, steps: e.target.value })}
                  required
                  placeholder="1. Step one&#10;2. Step two"
                  className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 resize-none"
                />
              </div>

              <div>
                <label className="text-xs font-mono text-slate-400">Expected Result</label>
                <input
                  type="text"
                  value={formData.expected_result}
                  onChange={e => setFormData({ ...formData, expected_result: e.target.value })}
                  required
                  placeholder="HTTP 200 returned with valid payload..."
                  className="w-full bg-[#162035] border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                />
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
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold"
                >
                  Save Test Case
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
