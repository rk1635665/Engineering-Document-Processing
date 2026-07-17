export const STATUS_TONES = {
  queued: {
    label: "Queued",
    dot: "bg-slate-400",
    text: "text-slate-600",
    bg: "bg-slate-100",
  },
  processing: {
    label: "Processing",
    dot: "bg-blue-500 animate-pulse",
    text: "text-blue-700",
    bg: "bg-blue-50",
  },
  review: {
    label: "Needs Review",
    dot: "bg-warning",
    text: "text-warning",
    bg: "bg-warning-bg",
  },
  completed: {
    label: "Completed",
    dot: "bg-success",
    text: "text-success",
    bg: "bg-success-bg",
  },
  failed: {
    label: "Failed",
    dot: "bg-danger",
    text: "text-danger",
    bg: "bg-danger-bg",
  },
};

export function getConfidenceTone(value) {
  if (value >= 90) {
    return { label: "High", text: "text-success", bg: "bg-success-bg" };
  }
  if (value >= 70) {
    return { label: "Medium", text: "text-warning", bg: "bg-warning-bg" };
  }
  return { label: "Low", text: "text-danger", bg: "bg-danger-bg" };
}