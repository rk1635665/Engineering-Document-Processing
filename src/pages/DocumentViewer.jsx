import { useState, useEffect } from "react";
import { ZoomIn, ZoomOut, RotateCw, Download, ChevronLeft, ChevronRight, Terminal, ChevronDown, ChevronUp, Sparkles, Loader2 } from "lucide-react";
import Card from "../components/Card";
import ConfidenceBadge from "../components/ConfidenceBadge";
import FloatingChat from "../components/FloatingChat";
import FilePreview from "../components/FilePreview";
import { useSearchParams } from "react-router-dom";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function DocumentViewer() {
  const [searchParams] = useSearchParams();
  const documentId = searchParams.get("id");
  
  const [docDetails, setDocDetails] = useState(null);
  const [fields, setFields] = useState([]);
  const [loading, setLoading] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [showConsole, setShowConsole] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: "assistant",
      text: "I've extracted the data from this document. You can ask me questions about specific fields or request formatting changes.",
    },
  ]);

  useEffect(() => {
    if (!documentId) return;
    
    async function fetchDocumentData() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}`);
        if (response.ok) {
          const data = await response.json();
          setDocDetails(data);
          // extractedFields comes back camelCase (CamelModel alias), same
          // convention as every other endpoint in this app
          setFields(data.extractedFields || []);
        }
      } catch (err) {
        console.error("Failed fetching doc viewer endpoints:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchDocumentData();
  }, [documentId]);

  // While extraction is still running, poll for status changes so the
  // progress bar clears and the extracted fields appear automatically —
  // no manual refresh needed. Stops as soon as the doc leaves
  // queued/processing (or on unmount).
  useEffect(() => {
    if (!documentId) return;
    if (docDetails?.status !== "queued" && docDetails?.status !== "processing") return;

    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}`);
        if (response.ok) {
          const data = await response.json();
          setDocDetails(data);
          setFields(data.extractedFields || []);
        }
      } catch (err) {
        console.error("Polling for extraction status failed:", err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [documentId, docDetails?.status]);

  const handleSendMessage = async (text) => {
    setMessages((prev) => [...prev, { id: prev.length + 1, role: "user", text }]);
    try {
      const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = response.ok ? await response.json() : null;
      setMessages((prev) => [
        ...prev,
        { id: prev.length + 1, role: "assistant", text: data?.reply || "I couldn't reach the extraction context for this document." },
      ]);
    } catch (err) {
      setMessages((prev) => [...prev, { id: prev.length + 1, role: "assistant", text: "Chat is temporarily unavailable." }]);
    }
  };

  if (!documentId) {
    return <div className="p-6 text-slate-500 text-center">No document specified. Navigate from the Documents list to view a file.</div>;
  }

  return (
    <div className="flex flex-col h-full space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl font-semibold text-ink">Document Viewer</h2>
      </div>

      {/* Document context — type/revision/status/upload metadata for this file */}
      {docDetails && (
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs font-mono text-slate-500 bg-paper border border-line rounded-lg px-4 py-2">
          <span><span className="text-slate-400">Type:</span> {docDetails.type}</span>
          <span><span className="text-slate-400">Revision:</span> {docDetails.revision}</span>
          <span><span className="text-slate-400">Status:</span> {docDetails.status}</span>
          {docDetails.extractionMethod && (
            <span><span className="text-slate-400">Extracted with:</span> {docDetails.extractionMethod}</span>
          )}
          <span><span className="text-slate-400">Pages:</span> {docDetails.pageCount}</span>
          <span><span className="text-slate-400">Uploaded:</span> {docDetails.uploadedAt ? new Date(docDetails.uploadedAt).toLocaleString() : "—"}</span>
          {docDetails.reviewerComment && (
            <span className="text-warning"><span className="text-slate-400">Note:</span> {docDetails.reviewerComment}</span>
          )}
        </div>
      )}

      {/* Extraction progress — no real percentage is tracked server-side
          (it's a single background task, not staged), so this is an
          honest indeterminate bar rather than a fabricated number. Polling
          above clears it automatically the moment status changes. */}
      {(docDetails?.status === "queued" || docDetails?.status === "processing") && (
        <div className="bg-paper border border-line rounded-lg px-4 py-3">
          <div className="flex items-center gap-2 text-xs font-mono text-slate-500 mb-2">
            <Loader2 size={14} className="animate-spin text-blue-500" />
            {docDetails.status === "queued" ? "Queued for extraction…" : "Extraction in progress…"}
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
            <div className="h-full w-2/3 rounded-full bg-blue-500 animate-pulse" />
          </div>
        </div>
      )}

      {/* AI Insight — one-shot summary generated by Qwen/Llava at extraction time, grounded on this document's own extracted fields */}
      {docDetails?.insight && (
        <Card padding="p-4">
          <h3 className="font-display text-sm font-semibold text-ink mb-1 flex items-center gap-2">
            <Sparkles size={16} className="text-blue-500" />
            AI Insight
          </h3>
          <p className="text-sm text-slate-600">{docDetails.insight}</p>
        </Card>
      )}

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-0">
        {/* Left: Viewer Container */}
        <Card padding="p-0" className="flex flex-col min-h-0">
          <div className="p-3 border-b border-line flex items-center justify-between bg-white rounded-t-xl">
            <div className="flex items-center gap-2 min-w-0">
              <span className="font-medium text-sm text-ink truncate">
                {loading ? "Loading..." : docDetails?.name || "Document View"}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))} className="p-1.5 text-slate-500 hover:bg-slate-100 rounded"><ZoomOut size={16} /></button>
              <span className="text-xs font-mono text-slate-500 w-10 text-center">{Math.round(zoom * 100)}%</span>
              <button onClick={() => setZoom((z) => Math.min(3, +(z + 0.25).toFixed(2)))} className="p-1.5 text-slate-500 hover:bg-slate-100 rounded"><ZoomIn size={16} /></button>
              <button onClick={() => setZoom(1)} className="p-1.5 text-slate-500 hover:bg-slate-100 rounded"><RotateCw size={16} /></button>
              <div className="w-px h-4 bg-line mx-1" />
              <button 
                onClick={() => window.open(`${API_BASE_URL}/api/documents/${documentId}/download`, '_blank')}
                className="p-1.5 text-slate-500 hover:bg-slate-100 rounded"
              >
                <Download size={16} />
              </button>
            </div>
          </div>
          <div className="flex-1 bg-blueprint-grid bg-slate-50 flex items-center justify-center relative overflow-auto">
             <FilePreview fileUrl={docDetails?.fileUrl} name={docDetails?.name} apiBaseUrl={API_BASE_URL} scale={zoom} />
          </div>
          <div className="p-2 border-t border-line bg-white flex items-center justify-center gap-3 rounded-b-xl">
            <button className="p-1 text-slate-400 hover:text-ink"><ChevronLeft size={16} /></button>
            <span className="text-xs font-mono text-slate-500">Page 1 of 1</span>
            <button className="p-1 text-slate-400 hover:text-ink"><ChevronRight size={16} /></button>
          </div>
        </Card>

        {/* Middle: Live Extracted Table */}
        <Card title="Extracted Information" padding="p-0" className="flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto scrollbar-thin">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="sticky top-0 bg-paper z-10 border-b border-line">
                <tr>
                  <th className="px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-wider text-slate-500">Field</th>
                  <th className="px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-wider text-slate-500">Value</th>
                  <th className="px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-wider text-slate-500 text-right">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line bg-white">
                {fields.length === 0 ? (
                  <tr>
                    <td colSpan="3" className="px-4 py-8 text-center text-slate-400">
                      {loading ? "Reading extraction..." : "No items extracted from this record structure."}
                    </td>
                  </tr>
                ) : (
                  fields.map((f, idx) => (
                    <tr key={f.id || idx} className="hover:bg-slate-50">
                      <td className="px-4 py-3 text-slate-600 font-medium">{f.label || f.key}</td>
                      <td className="px-4 py-3 text-ink font-mono text-xs">{f.value}</td>
                      <td className="px-4 py-3 text-right"><ConfidenceBadge value={f.confidence || 100} /></td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <FloatingChat messages={messages} onSendMessage={handleSendMessage} />

      {/* Debug console — raw payload as returned by the backend, for verifying what's actually populating the UI */}
      <div className="w-full max-w-full border border-line rounded-xl bg-white shadow-sm overflow-hidden">
        <button
          onClick={() => setShowConsole((v) => !v)}
          className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-xl"
        >
          <span className="flex items-center gap-2"><Terminal size={14} /> Raw Backend Data</span>
          {showConsole ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        {showConsole && (
          <pre className="max-h-80 w-full overflow-x-auto overflow-y-auto whitespace-pre-wrap break-words border-t border-line bg-slate-900 text-emerald-300 text-[11px] font-mono p-4 rounded-b-xl">
            {JSON.stringify({ docDetails, extractedFields: fields }, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}