import {
  LayoutDashboard,
  Upload,
  Files,
  FileImage,
  Database,
  GitCompareArrows,
  ClipboardCheck,
  Search,
  Settings,
} from "lucide-react";

export const navItems = [
  {
    label: "Dashboard",
    path: "/",
    icon: LayoutDashboard,
    description: "Overview & metrics",
  },
  {
    label: "Upload Documents",
    path: "/upload",
    icon: Upload,
    description: "Upload new files",
  },
  {
    label: "Documents",
    path: "/documents",
    icon: Files,
    description: "All uploaded drawings & nameplates",
  },
  {
    label: "Document Viewer",
    path: "/viewer",
    icon: FileImage,
    description: "View document & AI extraction",
  },
  {
    label: "Extracted Data",
    path: "/extracted-data",
    icon: Database,
    description: "All extracted fields",
  },
  {
    label: "Compare Revisions",
    path: "/compare",
    icon: GitCompareArrows,
    description: "Revision diffing across drawing sets",
  },
  {
    label: "Review & Validation",
    path: "/review",
    icon: ClipboardCheck,
    description: "Validate extracted fields",
  },
  {
    label: "Search",
    path: "/search",
    icon: Search,
    description: "Search system",
  },
];

export const secondaryNavItems = [
  {
    label: "Settings",
    path: "/settings",
    icon: Settings,
    description: "Preferences",
  },
];