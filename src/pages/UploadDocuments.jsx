import { useCallback, useRef, useState } from "react";
import {
  UploadCloud,
  FileText,
  Image as ImageIcon,
  X,
  RotateCw,
  Eye,
} from "lucide-react";
import Card from "../components/Card";
import Table from "../components/Table";
import StatusBadge from "../components/StatusBadge";
import { Link } from "react-router-dom";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const ACCEPTED_TYPES = ["application/pdf", "image/png", "image/jpeg", "image/tiff"];
const ACCEPTED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"];
const MAX_SIZE_BYTES = 100 * 1024 * 1024; // 100 MB

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}

function isAcceptedFile(file) {
  const extOk = ACCEPTED_EXTENSIONS.some((ext) =>
    file.name.toLowerCase().endsWith(ext)
  );
  const typeOk = ACCEPTED_TYPES.includes(file.type) || file.type === "";
  return extOk && typeOk;
}

function FileTypeIcon({ name }) {
  const isImage = /\.(png|jpe?g|tiff?)$/i.test(name);
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-500">
      {isImage ? (
        <ImageIcon size={15} strokeWidth={1.75} />
      ) : (
        <FileText size={15} strokeWidth={1.75} />
      )}
    </span>
  );
}

function ProgressBar({ value, status }) {
  const barColor = status === "failed" ? "bg-danger" : "bg-blue-500";
  return (
    <div className="flex items-center gap-3 w-48">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line">
        <div
          className={["h-full rounded-full transition-all duration-300", barColor].join(" ")}
          style={{ width: `${value}%` }}
        />
      </div>
      <span className="font-mono text-xs text-slate-500 w-8">{value}%</span>
    </div>
  );
}

let nextId = 1;

export default function UploadDocuments() {
  const [queue, setQueue] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const startRealUpload = useCallback(async (id, file) => {
    try {
      const formData = new FormData();
      formData.append("file", file);

      const xhr = new XMLHttpRequest();
      // Hits your FastAPI documents router upload endpoint directly
      xhr.open("POST", `${API_BASE_URL}/api/documents/upload`);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100);
          setQueue((prev) =>
            prev.map((item) =>
              item.id === id ? { ...item, progress: Math.min(percentComplete, 99) } : item
            )
          );
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          setQueue((prev) =>
            prev.map((item) =>
              item.id === id ? { ...item, status: "completed", progress: 100 } : item
            )
          );
        } else {
          setQueue((prev) =>
            prev.map((item) =>
              item.id === id ? { ...item, status: "failed", error: `Server error: ${xhr.status}` } : item
            )
          );
        }
      };

      xhr.onerror = () => {
        setQueue((prev) =>
          prev.map((item) =>
            item.id === id ? { ...item, status: "failed", error: "Network connection failed" } : item
          )
        );
      };

      xhr.send(formData);
    } catch (err) {
      setQueue((prev) =>
        prev.map((item) =>
          item.id === id ? { ...item, status: "failed", error: "Upload failed to execute" } : item
        )
      );
    }
  }, []);

  const addFiles = useCallback(
    (fileList) => {
      const incoming = Array.from(fileList).map((file) => {
        const accepted = isAcceptedFile(file);
        const withinSize = file.size <= MAX_SIZE_BYTES;
        const ok = accepted && withinSize;
        const itemId = nextId++;

        return {
          id: itemId,
          name: file.name,
          type: file.type.includes('pdf') ? 'Document' : 'Image',
          size: formatBytes(file.size),
          status: ok ? "processing" : "failed",
          progress: 0,
          error: !accepted
            ? "Unsupported format"
            : !withinSize
            ? "Exceeds 100 MB limit"
            : null,
          rawFile: ok ? file : null
        };
      });

      setQueue((prev) => [...incoming, ...prev]);

      incoming.forEach((item) => {
        if (item.status === "processing" && item.rawFile) {
          startRealUpload(item.id, item.rawFile);
        }
      });
    },
    [startRealUpload]
  );

  function handleDrop(e) {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
  }

  function handleBrowseChange(e) {
    if (e.target.files?.length) addFiles(e.target.files);
    e.target.value = "";
  }

  function removeItem(id) {
    setQueue((prev) => prev.filter((item) => item.id !== id));
  }

  function retryItem(id) {
    const item = queue.find((q) => q.id === id);
    if (item && item.rawFile) {
      setQueue((prev) =>
        prev.map((q) =>
          q.id === id ? { ...q, status: "processing", progress: 0, error: null } : q
        )
      );
      startRealUpload(id, item.rawFile);
    }
  }

  const columns = [
    {
      key: "name",
      header: "File Name",
      render: (row) => (
        <div className="flex items-center gap-3">
          <FileTypeIcon name={row.name} />
          <div className="min-w-0">
            <p className="truncate font-medium text-ink">{row.name}</p>
            {row.error && <p className="text-xs text-danger">{row.error}</p>}
          </div>
        </div>
      ),
    },
    {
      key: "type",
      header: "Type",
      render: (row) => <span className="text-slate-600">{row.type}</span>
    },
    {
      key: "size",
      header: "Size",
      render: (row) => <span className="text-slate-600 font-mono text-xs">{row.size}</span>
    },
    {
      key: "status",
      header: "Status",
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      key: "progress",
      header: "Progress",
      render: (row) => <ProgressBar value={row.progress} status={row.status} />,
    },
    {
      key: "actions",
      header: "",
      width: "50px",
      render: (row) => (
        <div className="flex items-center justify-end gap-1">
          {row.status === "failed" && (
            <button
              type="button"
              aria-label="Retry upload"
              onClick={() => retryItem(row.id)}
              className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-blue-600"
            >
              <RotateCw size={15} strokeWidth={1.75} />
            </button>
          )}
          {row.status === "completed" && (
            <Link
              to="/viewer"
              aria-label="View document"
              className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-blue-600"
            >
              <Eye size={15} strokeWidth={1.75} />
            </Link>
          )}
          <button
            type="button"
            aria-label="Remove from queue"
            onClick={() => removeItem(row.id)}
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-red-50 hover:text-danger"
          >
            <X size={15} strokeWidth={1.75} />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <h2 className="font-display text-xl font-semibold text-ink">Upload Documents</h2>
      <Card padding="p-0" className="border-dashed border-2 bg-transparent">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={[
            "flex flex-col items-center justify-center px-6 py-16 text-center transition-colors rounded-xl",
            isDragging ? "bg-blue-50/50" : "bg-white",
          ].join(" ")}
        >
          <span className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-50 text-blue-600 mb-4">
            <UploadCloud size={28} strokeWidth={1.75} />
          </span>
          <p className="font-display text-lg font-semibold text-ink mb-1">
            Drag & drop documents here
          </p>
          <p className="text-sm text-slate-500 mb-6 max-w-md">
            Upload PDF drawings, PNG or JPG images of nameplates, or TIFF scans. The system will automatically classify and extract data.
          </p>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="rounded-lg bg-blue-500 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-600 shadow-sm"
          >
            Browse Files
          </button>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPTED_EXTENSIONS.join(",")}
            onChange={handleBrowseChange}
            className="hidden"
          />
          <div className="mt-6 flex flex-wrap items-center justify-center gap-2 text-xs text-slate-400">
            <span>Supported: PDF, PNG, JPG, TIFF</span>
            <span>•</span>
            <span>Max size: 100MB per file</span>
          </div>
        </div>
      </Card>

      <Card
        title="Upload Queue"
        padding="p-0"
        action={
          queue.length > 0 && (
            <span className="text-sm font-medium text-blue-600">
              {queue.length} file{queue.length > 1 ? "s" : ""}
            </span>
          )
        }
      >
        <Table
          columns={columns}
          rows={queue}
          emptyMessage="No files queued yet — drag documents in above to get started."
        />
      </Card>
    </div>
  );
}