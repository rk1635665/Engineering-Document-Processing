import { useMemo, useState, useEffect } from "react";
import { Search, Download, FileText, Filter } from "lucide-react";
import Card from "../components/Card";
import Table from "../components/Table";
import ConfidenceBadge from "../components/ConfidenceBadge";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function ExtractedData() {
  const [extractedRows, setExtractedRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [docTypeFilter, setDocTypeFilter] = useState("all");

  useEffect(() => {
    async function fetchGlobalFields() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/parts`);
        if (response.ok) {
          const data = await response.json();
          setExtractedRows(data);
        }
      } catch (err) {
        console.error("Failed to load extracted fields mapping table:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchGlobalFields();
  }, []);

  const docTypeOptions = useMemo(
    () => ["all", ...new Set(extractedRows.map((r) => r.documentType || "Document"))],
    [extractedRows]
  );

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    return extractedRows.filter((row) => {
      const partNum = row.partNumber || "";
      const mat = row.material || "";
      const srcDoc = row.sourceDocument || "";
      const docType = row.documentType || "Document";

      const matchesSearch =
        !query ||
        partNum.toLowerCase().includes(query) ||
        mat.toLowerCase().includes(query) ||
        srcDoc.toLowerCase().includes(query);
      const matchesDocType = docTypeFilter === "all" || docType === docTypeFilter;
      return matchesSearch && matchesDocType;
    });
  }, [search, docTypeFilter, extractedRows]);

  const columns = [
    {
      key: "partNumber",
      header: "Part Number",
      render: (row) => <span className="font-mono text-xs font-medium text-ink">{row.partNumber || "N/A"}</span>,
    },
    { key: "material", header: "Material", render: (row) => <span>{row.material || "Steel"}</span> },
    {
      key: "revision",
      header: "Revision",
      render: (row) => <span className="font-mono text-xs text-slate-600">{row.revision || "A"}</span>,
    },
    {
      key: "dimensions",
      header: "Dimensions",
      render: (row) => <span className="font-mono text-xs text-slate-600">{row.dimensions || "—"}</span>,
    },
    {
      key: "tolerance",
      header: "Tolerance",
      render: (row) => <span className="font-mono text-xs text-slate-600">{row.tolerance || "—"}</span>,
    },
    {
      key: "confidence",
      header: "Confidence",
      render: (row) => <ConfidenceBadge value={row.confidence || 95} />,
    },
    {
      key: "sourceDocument",
      header: "Source Document",
      render: (row) => (
        <div className="flex items-center gap-2 text-slate-600">
          <FileText size={14} strokeWidth={1.75} className="shrink-0 text-slate-400" />
          <span className="truncate">{row.sourceDocument || "File.pdf"}</span>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
         <h2 className="font-display text-xl font-semibold text-ink">Extracted Data</h2>
      </div>

      <Card padding="p-0">
        <div className="p-4 border-b border-line flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1 max-w-md">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search extracted fields..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-lg border border-line text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none bg-paper"
            />
          </div>
          <div className="flex gap-3">
            <div className="relative flex-1 sm:w-48">
              <select
                value={docTypeFilter}
                onChange={(e) => setDocTypeFilter(e.target.value)}
                className="w-full appearance-none pl-3 pr-8 py-2 rounded-lg border border-line text-sm text-ink focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none bg-paper"
              >
                {docTypeOptions.map(d => (
                  <option key={d} value={d}>{d === 'all' ? 'All Document Types' : d}</option>
                ))}
              </select>
              <Filter size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
            <button 
              onClick={() => window.open(`${API_BASE_URL}/api/parts/export`, '_blank')}
              className="flex items-center gap-1.5 rounded-lg border border-line bg-white px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
            >
               <Download size={15} strokeWidth={2} /> Export CSV
            </button>
          </div>
        </div>

        <Table
          columns={columns}
          rows={filteredRows}
          emptyMessage={loading ? "Loading active metrics repository..." : "No records match your search and filters."}
        />
        <div className="p-4 border-t border-line flex items-center justify-between text-sm text-slate-500">
           <span>Showing 1 to {filteredRows.length} of {filteredRows.length} entries</span>
           <div className="flex gap-1">
             <button className="px-3 py-1 border border-line rounded bg-paper disabled:opacity-50" disabled>Previous</button>
             <button className="px-3 py-1 border border-line rounded bg-paper disabled:opacity-50" disabled>Next</button>
           </div>
        </div>
      </Card>
    </div>
  );
}