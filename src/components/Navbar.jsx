import { useLocation } from "react-router-dom";
import { navItems, secondaryNavItems } from "../data/navigation";
import { Bell } from "lucide-react";

const allItems = [...navItems, ...secondaryNavItems];

function useCurrentPage() {
  const { pathname } = useLocation();
  return (
    allItems.find((item) =>
      item.path === "/" ? pathname === "/" : pathname.startsWith(item.path)
    ) || { label: "Dashboard", description: "Pipeline overview & recent activity" }
  );
}

export default function Navbar() {
  const current = useCurrentPage();

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-line bg-white px-6">
      <div>
        <h1 className="font-display text-lg font-semibold text-ink">
          {current.label}
        </h1>
        <p className="text-xs text-slate-500">{current.description}</p>
      </div>

      <div className="flex items-center gap-4">
        

        <button
          type="button"
          aria-label="Notifications"
          className="relative flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-paper hover:text-ink"
        >
          <Bell size={18} strokeWidth={1.75} />
          <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-blue-500" />
        </button>

        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-ink font-display text-xs font-semibold text-white">
          ED
        </div>
      </div>
    </header>
  );
}