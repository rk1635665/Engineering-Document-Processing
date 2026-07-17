import { useState, useMemo, useEffect } from "react";
import { Search, Filter, Upload, FileText, Eye, Download, Trash2 } from "lucide-react";
import Card from "../components/Card";
import Table from "../components/Table";
import StatusBadge from "../components/StatusBadge";
import ConfidenceBadge from "../components/ConfidenceBadge";
import { recentDocuments as mockDocuments } from "../data/mockDocuments";
import { Link } from "react-router-dom";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function Documents() {
  const [dbDocuments, setDbDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [deletingId, setDeletingId] = useState(null);

  async function fetchAllDocuments() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/documents`);
      if (response.ok) {
        const data = await response.json();
        // Trust the API even when it legitimately returns zero rows —
        // only fall back to mocks if the request itself failed.
        setDbDocuments(data);
      } else {
        setDbDocuments(mockDocuments);
      }
    } catch (err) {
      console.error("Could not fetch documents, falling back to local mocks", err);
      setDbDocuments(mockDocuments);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchAllDocuments();
  }, []);

  async function handleDelete(row) {
    if (!window.confirm(`Delete "${row.name}"? This removes the uploaded file and all extracted data — this can't be undone.`)) {
      return;
    }
    setDeletingId(row.id);
    try {
      const response = await fetch(`${API_BASE_URL}/api/documents/${row.id}`, { method: "DELETE" });
      if (response.ok || response.status === 204) {
        setDbDocuments((prev) => prev.filter((d) => d.id !== row.id));
      } else {
        alert("Could not delete this document. Please try again.");
      }
    } catch (err) {
      console.error("Delete failed:", err);
      alert("Could not reach the server to delete this document.");
    } finally {
      setDeletingId(null);
    }
  }

  const getExt = (doc) => (doc.name || "").split(".").pop()?.toLowerCase() || "file";

  const types = useMemo(() => ["all", ...new Set(dbDocuments.map(getExt))], [dbDocuments]);
  const statuses = useMemo(() => ["all", ...new Set(dbDocuments.map(d => d.status || "completed"))], [dbDocuments]);

  const filteredDocs = useMemo(() => {
    return dbDocuments.filter(doc => {
      const nameStr = doc.name || "";
      const typeStr = getExt(doc);
      const statusStr = doc.status || "completed";

      const matchesSearch = nameStr.toLowerCase().includes(search.toLowerCase());
      const matchesType = typeFilter === "all" || typeStr === typeFilter;
      const matchesStatus = statusFilter === "all" || statusStr === statusFilter;
      return matchesSearch && matchesType && matchesStatus;
    });
  }, [dbDocuments, search, typeFilter, statusFilter]);

  const columns = [
    {
      key: "name",
      header: "Document Name",
      render: (row) => (
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-blue-50 text-blue-600">
            <FileText size={15} strokeWidth={1.75} />
          </span>
          <span className="font-medium text-ink">{row.name}</span>
        </div>
      ),
    },
    {
      key: "type",
      header: "Type",
      render: (row) => {
        const ext = (row.name || "").split(".").pop();
        return <span className="text-slate-600 uppercase font-mono text-xs">{ext || "file"}</span>;
      },
    },
    {
      key: "confidence",
      header: "Confidence",
      render: (row) => row.confidence != null ? <ConfidenceBadge value={row.confidence} /> : <span className="text-slate-400 text-xs">—</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (row) => <StatusBadge status={row.status || "completed"} />,
    },
    {
      key: "uploaded",
      header: "Uploaded On",
      render: (row) => {
        const date = row.created_at || row.uploaded_at;
        return (
          <span className="text-slate-600">
            {date ? new Date(date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : "Jul 8, 2026"}
          </span>
        );
      }
    },
    {
      key: "action",
      header: "Action",
      render: (row) => (
        <div className="flex items-center gap-2">
          <Link
            to={`/viewer?id=${row.id}`}
            aria-label="View document"
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-100 hover:text-blue-600"
          >
            <Eye size={16} strokeWidth={1.75} />
          </Link>
          <button
            type="button"
            onClick={() => window.open(`${API_BASE_URL}/api/documents/${row.id}/download`, '_blank')}
            aria-label="Download document"
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-100 hover:text-blue-600"
          >
            <Download size={16} strokeWidth={1.75} />
          </button>
          <button
            type="button"
            onClick={() => handleDelete(row)}
            disabled={deletingId === row.id}
            aria-label="Delete document"
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-red-50 hover:text-danger disabled:opacity-40"
          >
            <Trash2 size={16} strokeWidth={1.75} />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h2 className="font-display text-xl font-semibold text-ink">Documents</h2>
        <Link
          to="/upload"
          className="flex items-center gap-1.5 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-600"
        >
          <Upload size={16} strokeWidth={2} />
          Upload Documents
        </Link>
      </div>

      <Card padding="p-0">
        <div className="p-4 border-b border-line flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1 max-w-md">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search documents..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-lg border border-line text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
            />
          </div>
          <div className="flex gap-3">
            <div className="relative flex-1 sm:w-40">
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="w-full appearance-none pl-3 pr-8 py-2 rounded-lg border border-line text-sm text-ink focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
              >
                {types.map(t => (
                  <option key={t} value={t}>{t === 'all' ? 'All Types' : t}</option>
                ))}
              </select>
              <Filter size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
            <div className="relative flex-1 sm:w-40">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="w-full appearance-none pl-3 pr-8 py-2 rounded-lg border border-line text-sm text-ink focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
              >
                {statuses.map(s => (
                  <option key={s} value={s}>
                    {s === 'all' ? 'All Statuses' : s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
              <Filter size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>
        </div>
        <Table columns={columns} rows={filteredDocs} emptyMessage={loading ? "Loading documents..." : "No documents found."} />
        <div className="p-4 border-t border-line flex items-center justify-between text-sm text-slate-500">
           <span>Showing 1 to {filteredDocs.length} of {filteredDocs.length} entries</span>
           <div className="flex gap-1">
             <button className="px-3 py-1 border border-line rounded bg-paper disabled:opacity-50" disabled>Previous</button>
             <button className="px-3 py-1 border border-line rounded bg-paper disabled:opacity-50" disabled>Next</button>
           </div>
        </div>
      </Card>
    </div>
  );
}