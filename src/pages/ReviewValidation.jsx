import { useState, useEffect } from "react";
import { ChevronLeft, Check, X, AlertCircle, CheckCircle2 } from "lucide-react";
import Card from "../components/Card";
import FloatingChat from "../components/FloatingChat";
import ConfidenceBadge from "../components/ConfidenceBadge";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import StatusBadge from "../components/StatusBadge";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function ReviewValidation() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const documentId = searchParams.get("id");

  const [documentName, setDocumentName] = useState("Loading Document...");
  const [fields, setFields] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: "assistant",
      text: "I flagged a few fields for review due to low confidence scores. You can verify them against the original photo.",
    },
  ]);

  useEffect(() => {
    if (!documentId) return;
    async function fetchReviewData() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}`);
        if (response.ok) {
          const data = await response.json();
          setDocumentName(data.name);
          setFields(data.extractedFields || []);
        }
      } catch (err) {
        console.error("Error reading validation payload entries:", err);
      }
    }
    fetchReviewData();
  }, [documentId]);

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

  const updateFieldValue = (id, val) => {
    setFields(prev => prev.map((f, idx) => (f.id === id || idx === id) ? { ...f, yourValue: val } : f));
  };

  const handleValidationAction = async (status) => {
    if (!documentId) return;
    setSubmitting(true);
    try {
      // Push any values a human edited in "Your Value" back to their
      // ReviewField rows before recording the decision.
      const changed = fields.filter((f) => f.yourValue !== undefined && f.yourValue !== f.value);
      await Promise.all(
        changed.map((f) =>
          fetch(`${API_BASE_URL}/api/documents/${documentId}/review-fields/${f.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ value: f.yourValue }),
          })
        )
      );

      const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (response.ok) {
        navigate("/documents");
      }
    } catch (err) {
      console.error("Failed compiling form verification submission:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const lowConfidenceCount = fields.filter(f => (f.confidence || 100) < 70).length;

  if (!documentId) {
    return <div className="p-6 text-slate-500 text-center">No reference ID targeted for validation review.</div>;
  }

  return (
    <div className="flex flex-col h-full space-y-4">
      <div className="flex items-center gap-2 text-sm text-slate-500 font-medium">
         <Link to="/documents" className="hover:text-ink flex items-center gap-1"><ChevronLeft size={16}/> Documents</Link>
         <span>/</span>
         <span className="text-ink">Review & Validation</span>
      </div>
      
      <div className="flex items-center justify-between">
         <div className="flex items-center gap-3">
            <h2 className="font-display text-xl font-semibold text-ink">{documentName}</h2>
            <StatusBadge status="review" />
         </div>
      </div>

      <div className="flex-1 flex flex-col gap-6 min-h-0">
        <Card className="flex-1 flex flex-col min-h-0" padding="p-0">
          <div className="flex-1 overflow-y-auto scrollbar-thin">
            <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="sticky top-0 bg-paper z-10 border-b border-line">
                  <tr>
                    <th className="px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-wider text-slate-500">Field</th>
                    <th className="px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-wider text-slate-500">Extracted Value</th>
                    <th className="px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-wider text-slate-500">Confidence</th>
                    <th className="px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-wider text-slate-500">Your Value</th>
                    <th className="px-4 py-3 font-mono text-[11px] font-medium uppercase tracking-wider text-slate-500">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line bg-white">
                  {fields.map((f, idx) => {
                     const identifier = f.id !== undefined ? f.id : idx;
                     const isLow = (f.confidence || 100) < 70;
                     return (
                      <tr key={identifier} className="hover:bg-slate-50">
                        <td className="px-4 py-4 text-slate-700 font-medium">{f.label || f.key}</td>
                        <td className="px-4 py-4 font-mono text-xs text-ink">{f.value}</td>
                        <td className="px-4 py-4"><ConfidenceBadge value={f.confidence || 100} /></td>
                        <td className="px-4 py-4">
                           <input 
                              type="text"
                              value={f.yourValue ?? f.value}
                              onChange={(e) => updateFieldValue(identifier, e.target.value)}
                              className={`w-full px-2 py-1.5 text-sm border rounded bg-white focus:outline-none focus:border-blue-500 font-mono text-xs
                                 ${isLow ? 'border-warning focus:ring-1 focus:ring-warning' : 'border-line focus:ring-1 focus:ring-blue-500'}`}
                           />
                        </td>
                        <td className="px-4 py-4">
                           {isLow ? <AlertCircle size={16} className="text-warning" /> : <CheckCircle2 size={16} className="text-success" />}
                        </td>
                      </tr>
                  )})}
                </tbody>
            </table>
          </div>
          <div className="p-4 border-t border-line bg-paper flex items-center justify-between">
             <div className="text-sm text-slate-500">
                <span className="font-medium text-ink">{lowConfidenceCount}</span> fields require review
             </div>
             <div className="flex items-center gap-3">
                <button 
                  disabled={submitting}
                  onClick={() => handleValidationAction("rejected")}
                  className="flex items-center gap-1.5 rounded-lg border border-line bg-white px-4 py-2 text-sm font-medium text-danger transition-colors hover:bg-danger-bg disabled:opacity-50"
                >
                  <X size={16} strokeWidth={2} /> Reject All
                </button>
                <button 
                  disabled={submitting}
                  onClick={() => handleValidationAction("approved")}
                  className="flex items-center gap-1.5 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-600 disabled:opacity-50"
                >
                  <Check size={16} strokeWidth={2} /> Approve Document
                </button>
             </div>
          </div>
        </Card>
      </div>

      <FloatingChat messages={messages} onSendMessage={handleSendMessage} />
    </div>
  );
}