import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Navbar from "./components/Navbar";
import Dashboard from "./pages/Dashboard";
import UploadDocuments from "./pages/UploadDocuments";
import Documents from "./pages/Documents";
import DocumentViewer from "./pages/DocumentViewer";
import ExtractedData from "./pages/ExtractedData";
import CompareRevisions from "./pages/CompareRevisions";
import ReviewValidation from "./pages/ReviewValidation";
import { navItems, secondaryNavItems } from "./data/navigation";

function RouteStub({ label }) {
  return (
    <div className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-line text-center bg-white">
      <p className="font-mono text-xs uppercase tracking-widest text-slate-400">
        Route connected
      </p>
      <p className="mt-1 font-display text-lg font-semibold text-ink">{label}</p>
      <p className="mt-1 text-sm text-slate-500">Page content coming soon.</p>
    </div>
  );
}

export default function App() {
  const routableItems = [...navItems, ...secondaryNavItems];

  return (
    <div className="flex h-screen bg-paper overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col h-full overflow-hidden">
        <Navbar />
        <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<UploadDocuments />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/viewer" element={<DocumentViewer />} />
            <Route path="/extracted-data" element={<ExtractedData />} />
            <Route path="/compare" element={<CompareRevisions />} />
            <Route path="/review" element={<ReviewValidation />} />
            {routableItems
              .filter(
                (item) =>
                  !["/", "/upload", "/documents", "/viewer", "/extracted-data", "/compare", "/review"].includes(item.path)
              )
              .map((item) => (
                <Route
                  key={item.path}
                  path={item.path}
                  element={<RouteStub label={item.label} />}
                />
              ))}
          </Routes>
        </main>
      </div>
    </div>
  );
}