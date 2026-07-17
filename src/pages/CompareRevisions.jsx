import { useState, useEffect } from "react";
import { GitCompareArrows } from "lucide-react";
import Card from "../components/Card";
import FloatingChat from "../components/FloatingChat";
import FilePreview from "../components/FilePreview";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function CompareRevisions() {
  const [availableDocs, setAvailableDocs] = useState([]);
  const [revisionA, setRevisionA] = useState("");
  const [revisionB, setRevisionB] = useState("");
  const [revisionC, setRevisionC] = useState("");
  const [docADetail, setDocADetail] = useState(null);
  const [docBDetail, setDocBDetail] = useState(null);
  const [docCDetail, setDocCDetail] = useState(null);
  const [diffSummary, setDiffSummary] = useState([]);
  const [insights, setInsights] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: "assistant",
      text: "Select any two (or all three) document references above to calculate structural attribute variance logs.",
    },
  ]);

  useEffect(() => {
    async function loadSelectors() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/documents`);
        if (response.ok) {
          const data = await response.json();
          setAvailableDocs(data);
          if (data.length > 0) setRevisionA(data[0].id);
          if (data.length > 1) setRevisionB(data[1].id);
        }
      } catch (err) {
        console.error("Failed to load historical selection nodes:", err);
      }
    }
    loadSelectors();
  }, []);

  useEffect(() => {
    if (!revisionA) { setDocADetail(null); return; }
    fetch(`${API_BASE_URL}/api/documents/${revisionA}`).then(r => r.ok ? r.json() : null).then(setDocADetail);
  }, [revisionA]);

  useEffect(() => {
    if (!revisionB) { setDocBDetail(null); return; }
    fetch(`${API_BASE_URL}/api/documents/${revisionB}`).then(r => r.ok ? r.json() : null).then(setDocBDetail);
  }, [revisionB]);

  useEffect(() => {
    if (!revisionC) { setDocCDetail(null); return; }
    fetch(`${API_BASE_URL}/api/documents/${revisionC}`).then(r => r.ok ? r.json() : null).then(setDocCDetail);
  }, [revisionC]);

  // The three dropdowns are independent panes (Base / Target / Revision C),
  // any of which can be left empty. "Active" = currently has a document
  // picked. We only need >=2 active to run a comparison — which two (or
  // all three) doesn't matter, so every combination (A+B, A+C, B+C, A+B+C)
  // is supported the same way: send whichever active docs there are, in
  // pane order, as docA/docB/(docC) to the API.
  const slots = [
    { key: "A", id: revisionA, detail: docADetail },
    { key: "B", id: revisionB, detail: docBDetail },
    { key: "C", id: revisionC, detail: docCDetail },
  ];
  const activeSlots = slots.filter((s) => s.id);

  // Maps each pane's letter (A/B/C) to its position in the current API
  // call (also A/B/C, but reassigned based on which panes are actually
  // filled) — e.g. if only Target(B) and Revision C(C) are picked, B
  // becomes the API's docA and C becomes docB. Used to pull the right
  // boundingBox/revision value back out of the response for each pane.
  const apiLetterBySlot = {};
  activeSlots.forEach((s, i) => { apiLetterBySlot[s.key] = ["A", "B", "C"][i]; });

  useEffect(() => {
    if (activeSlots.length < 2) {
      setDiffSummary([]);
      setInsights("");
      return;
    }
    async function calculateDifferences() {
      setLoading(true);
      try {
        const params = new URLSearchParams({ docA: activeSlots[0].id, docB: activeSlots[1].id });
        if (activeSlots.length === 3) params.set("docC", activeSlots[2].id);
        const response = await fetch(`${API_BASE_URL}/api/compare?${params}`);
        if (response.ok) {
          const data = await response.json();
          setDiffSummary(data.differences || []);
          setInsights(data.insights || "");
        }
      } catch (err) {
        console.error("Comparison run failure:", err);
      } finally {
        setLoading(false);
      }
    }
    calculateDifferences();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revisionA, revisionB, revisionC]);

  const handleSendMessage = async (text) => {
    setMessages((prev) => [...prev, { id: prev.length + 1, role: "user", text }]);
    const targetDoc = revisionC || revisionB || revisionA;
    if (!targetDoc) {
      setMessages((prev) => [...prev, { id: prev.length + 1, role: "assistant", text: "Select at least one document above first." }]);
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/documents/${targetDoc}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = response.ok ? await response.json() : null;
      setMessages((prev) => [
        ...prev,
        { id: prev.length + 1, role: "assistant", text: data?.reply || "I couldn't reach the extraction context for these documents." },
      ]);
    } catch (err) {
      setMessages((prev) => [...prev, { id: prev.length + 1, role: "assistant", text: "Chat is temporarily unavailable." }]);
    }
  };

  const changesCount = {
    added: diffSummary.filter(d => d.status === 'added').length,
    removed: diffSummary.filter(d => d.status === 'removed').length,
    modified: diffSummary.filter(d => d.status === 'modified').length,
  };

  // One table column per currently-active pane, labeled with the real
  // file name (falls back to "Revision X" if the detail hasn't loaded
  // yet) so it's unambiguous which column belongs to which pane even
  // though the underlying API letter can shift between combinations.
  const activeColumns = activeSlots.map((s) => ({
    slotKey: s.key,
    apiLetter: apiLetterBySlot[s.key],
    label: s.detail?.name || `Revision ${apiLetterBySlot[s.key]}`,
  }));
  const colCount = 2 + activeColumns.length; // Attribute + Status + one per active pane

  function renderPane(slotKey, label, borderClass) {
    const detail = slotKey === "A" ? docADetail : slotKey === "B" ? docBDetail : docCDetail;
    const apiLetter = apiLetterBySlot[slotKey];
    const overlays = apiLetter
      ? diffSummary.filter((d) => d[`boundingBox${apiLetter}`])
      : [];
    return (
      <div className="flex-1 bg-blueprint-grid bg-slate-50 rounded-b-xl border-t border-line relative flex items-center justify-center overflow-auto">
        <FilePreview fileUrl={detail?.fileUrl} name={detail?.name} apiBaseUrl={API_BASE_URL} />
        {overlays.map((d) => (
          <div
            key={d.id}
            title={d.attribute}
            className={`absolute border-2 ${borderClass} rounded-sm pointer-events-none`}
            style={{
              top: d[`boundingBox${apiLetter}`].top,
              left: d[`boundingBox${apiLetter}`].left,
              width: d[`boundingBox${apiLetter}`].width,
              height: d[`boundingBox${apiLetter}`].height,
            }}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl font-semibold text-ink">Compare Revisions</h2>
      </div>

      <div className="flex flex-col gap-6 min-h-0">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 h-3/5">
          <Card padding="p-0" className="flex flex-col">
            <div className="p-3 border-b border-line flex items-center justify-between bg-white rounded-t-xl">
              <select
                value={revisionA}
                onChange={(e) => setRevisionA(e.target.value)}
                className="bg-paper border border-line rounded px-2 py-1 text-sm font-medium w-full max-w-xs"
              >
                <option value="">Select Base File</option>
                {availableDocs.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
            {renderPane("A", "Base File", "border-red-500")}
          </Card>

          <Card padding="p-0" className="flex flex-col">
            <div className="p-3 border-b border-line flex items-center justify-between bg-white rounded-t-xl">
              <select
                value={revisionB}
                onChange={(e) => setRevisionB(e.target.value)}
                className="bg-paper border border-line rounded px-2 py-1 text-sm font-medium w-full max-w-xs"
              >
                <option value="">Select Target File</option>
                {availableDocs.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
            {renderPane("B", "Target File", "border-green-500")}
          </Card>

          {/* Revision C is optional — leaving it empty just means the
              comparison runs on whichever two of the three panes are filled. */}
          <Card padding="p-0" className="flex flex-col">
            <div className="p-3 border-b border-line flex items-center justify-between bg-white rounded-t-xl">
              <select
                value={revisionC}
                onChange={(e) => setRevisionC(e.target.value)}
                className="bg-paper border border-line rounded px-2 py-1 text-sm font-medium w-full max-w-xs"
              >
                <option value="">Select Revision C (optional)</option>
                {availableDocs.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
            {renderPane("C", "Revision C", "border-amber-500")}
          </Card>
        </div>

        {insights && (
          <Card padding="p-4">
            <h3 className="font-display text-sm font-semibold text-ink mb-1">Comparison Insights</h3>
            <p className="text-sm text-slate-600">{insights}</p>
          </Card>
        )}

        <Card className="flex-1 flex flex-col min-h-0" padding="p-0">
          <div className="p-4 border-b border-line flex items-center justify-between">
            <h3 className="font-display text-sm font-semibold text-ink flex items-center gap-2">
              <GitCompareArrows size={16} className="text-blue-500" />
              Detected Changes
            </h3>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3 text-xs font-mono">
                <span className="text-warning">{changesCount.modified} Modified</span>
                <span className="text-success">{changesCount.added} Added</span>
                <span className="text-danger">{changesCount.removed} Removed</span>
              </div>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto scrollbar-thin">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="sticky top-0 bg-paper z-10 border-b border-line">
                <tr>
                  <th className="px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-wider text-slate-500">Attribute</th>
                  {activeColumns.map((col) => (
                    <th key={col.slotKey} className="px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-wider text-slate-500">
                      {col.label}
                    </th>
                  ))}
                  <th className="px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-wider text-slate-500">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line bg-white">
                {activeSlots.length < 2 ? (
                  <tr><td colSpan={colCount} className="text-center py-6 text-slate-400">Select at least two files above to compare.</td></tr>
                ) : loading ? (
                  <tr><td colSpan={colCount} className="text-center py-6 text-slate-400">Comparing files...</td></tr>
                ) : diffSummary.length === 0 ? (
                  <tr><td colSpan={colCount} className="text-center py-6 text-slate-400">No delta logs mapped for the selected assets.</td></tr>
                ) : (
                  diffSummary.map((diff, i) => (
                    <tr key={diff.id || i} className="hover:bg-slate-50">
                      <td className="px-4 py-3 text-slate-700 font-medium">{diff.attribute}</td>
                      {activeColumns.map((col) => (
                        <td key={col.slotKey} className="px-4 py-3 font-mono text-xs text-ink">
                          {diff[`revision${col.apiLetter}`] ?? "—"}
                        </td>
                      ))}
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide
                          ${diff.status === 'added' ? 'bg-success-bg text-success' :
                            diff.status === 'removed' ? 'bg-danger-bg text-danger' : 'bg-warning-bg text-warning'}`}>
                          {diff.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <FloatingChat messages={messages} onSendMessage={handleSendMessage} />
    </div>
  );
}
