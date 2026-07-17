import { FileStack, ListChecks, Target, ClockAlert } from "lucide-react";

// Mock summary metrics — stands in for an aggregated stats endpoint.
export const dashboardStats = [
  {
    id: "total-documents",
    label: "Total Documents",
    value: "1,284",
    icon: FileStack,
    trend: { direction: "up", value: "+8.2%", period: "vs last week" },
  },
  {
    id: "extracted-fields",
    label: "Extracted Fields",
    value: "9,562",
    icon: ListChecks,
    trend: { direction: "up", value: "+12.4%", period: "vs last week" },
  },
  {
    id: "extraction-accuracy",
    label: "Extraction Accuracy",
    value: "94.7%",
    icon: Target,
    trend: { direction: "up", value: "+1.1%", period: "vs last week" },
  },
  {
    id: "pending-reviews",
    label: "Pending Reviews",
    value: "23",
    icon: ClockAlert,
    trend: { direction: "down", value: "-5", period: "vs yesterday" },
    tone: "warning",
  },
];
