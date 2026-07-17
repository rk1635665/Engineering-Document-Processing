import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Eye, Download, FileText, Upload, FileStack, ListChecks, Target, ClockAlert, Trash2 } from "lucide-react";
import Card from "../components/Card";
import Table from "../components/Table";
import StatusBadge from "../components/StatusBadge";
import { dashboardStats as mockStats } from "../data/dashboardStats";
import { recentDocuments as mockDocuments } from "../data/mockDocuments";
import { Link } from "react-router-dom";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// The stats API returns id/label/value/trend/tone — everything except the
// icon, which is a frontend-only concern. Map by the same stable ids the
// backend uses (see StatCardOut in schemas.py).
const STAT_ICONS = {
  "total-documents": FileStack,
  "extracted-fields": ListChecks,
  "extraction-accuracy": Target,
  "pending-reviews": ClockAlert,
};

function StatCard({ stat }) {
  const Icon = stat.icon;
  const isWarning = stat.tone === "warning";
  const TrendIcon = stat.trend.direction === "up" ? TrendingUp : TrendingDown;
  const trendColor =
    stat.trend.direction === "up"
      ? isWarning
        ? "text-danger"
        : "text-success"
      : isWarning
      ? "text-success"
      : "text-danger";

  return (
    <Card padding="p-5" className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span
          className={[
            "flex h-10 w-10 items-center justify-center rounded-lg",
            isWarning ? "bg-warning-bg text-warning" : "bg-blue-50 text-blue-600",
          ].join(" ")}
        >
          <Icon size={20} strokeWidth={1.75} />
        </span>
        <span className={["flex items-center gap-1 text-xs font-medium", trendColor].join(" ")}>
          <TrendIcon size={14} strokeWidth={2} />
          {stat.trend.value}
        </span>
      </div>

      <div>
        <p className="font-display text-2xl font-bold text-ink">{stat.value}</p>
        <p className="text-sm font-medium text-slate-500">{stat.label}</p>
      </div>
    </Card>
  );
}

export default function Dashboard() {
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState(mockStats);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState(null);

  async function handleDelete(row) {
    if (!window.confirm(`Delete "${row.name}"? This can't be undone.`)) return;
    setDeletingId(row.id);
    try {
      const res = await fetch(`${API_BASE_URL}/api/documents/${row.id}`, { method: "DELETE" });
      if (res.ok) setDocuments((prev) => prev.filter((d) => d.id !== row.id));
      else alert("Could not delete this document.");
    } finally {
      setDeletingId(null);
    }
  }

  useEffect(() => {
    async function fetchStats() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/dashboard/stats`);
        if (response.ok) {
          const data = await response.json();
          setStats(data.map((s) => ({ ...s, icon: STAT_ICONS[s.id] || FileStack })));
        }
      } catch (err) {
        console.error("Failed to load dashboard stats, using mock data", err);
      }
    }
    fetchStats();
  }, []);

  useEffect(() => {
    async function fetchRecentDocuments() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/documents`);
        if (response.ok) {
          const data = await response.json();
          setDocuments(data.slice(0, 5));
        } else {
          setDocuments(mockDocuments);
        }
      } catch (err) {
        console.error("Failed to connect to backend, using mock data", err);
        setDocuments(mockDocuments);
      } finally {
        setLoading(false);
      }
    }
    fetchRecentDocuments();
  }, []);

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
    { key: "type", header: "Type", render: (row) => <span className="text-slate-600">{row.type || "Document"}</span> },
    {
      key: "revision",
      header: "Revision",
      render: (row) => <span className="font-mono text-xs text-slate-600">{row.revision || "A"}</span>,
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
            {date ? new Date(date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : "Just Now"}
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
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-paper hover:text-blue-600"
          >
            <Eye size={16} strokeWidth={1.75} />
          </Link>
          <button
            type="button"
            onClick={() => window.open(`${API_BASE_URL}/api/documents/${row.id}/download`, '_blank')}
            aria-label="Download document"
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-paper hover:text-blue-600"
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
      <div className="flex items-center justify-between">
         <h2 className="font-display text-xl font-semibold text-ink">Dashboard</h2>
         <Link
            to="/upload"
            className="flex items-center gap-1.5 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-600"
          >
            <Upload size={16} strokeWidth={2} />
            Upload Documents
          </Link>
      </div>
      
      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <StatCard key={stat.id} stat={stat} />
        ))}
      </div>

      {/* Recent documents */}
      <Card
        title="Recent Documents"
        padding="p-0"
        action={
          <Link
            to="/documents"
            className="text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            View All Documents
          </Link>
        }
      >
        <Table columns={columns} rows={documents} emptyMessage={loading ? "Loading documents..." : "No documents processed yet."} />
      </Card>
    </div>
  );
}