import { NavLink } from "react-router-dom";
import { Box } from "lucide-react";
import { navItems, secondaryNavItems } from "../data/navigation";

function NavRow({ item }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.path}
      end={item.path === "/"}
      title={item.description}
      className={({ isActive }) =>
        [
          "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
          isActive
            ? "bg-blue-50 text-blue-600 font-medium"
            : "text-slate-600 hover:bg-slate-100 hover:text-ink",
        ].join(" ")
      }
    >
      {({ isActive }) => (
        <>
          <Icon size={18} strokeWidth={isActive ? 2 : 1.75} className="shrink-0" />
          <span className="truncate">{item.label}</span>
        </>
      )}
    </NavLink>
  );
}

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col bg-white border-r border-line text-ink">
      {/* Brand mark */}
      <div className="flex items-center gap-3 px-5 py-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500">
          <Box size={18} className="text-white" strokeWidth={2} />
        </div>
        <p className="font-display text-lg font-bold text-ink">EDP</p>
      </div>

      <div className="mx-5 h-px bg-line" />

      {/* Primary nav */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4 scrollbar-thin">
        {navItems.map((item) => (
          <NavRow key={item.path} item={item} />
        ))}
      </nav>

      {/* Secondary nav */}
      <div className="space-y-1 border-t border-line px-3 py-4">
        {secondaryNavItems.map((item) => (
          <NavRow key={item.path} item={item} />
        ))}
      </div>
    </aside>
  );
}