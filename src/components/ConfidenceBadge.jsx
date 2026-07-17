import { getConfidenceTone } from "../data/badgeConfig";

export default function ConfidenceBadge({ value, showLabel = false }) {
  const tone = getConfidenceTone(value);

  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] font-medium",
        tone.text,
        tone.bg,
      ].join(" ")}
    >
      {value}%
      {showLabel && <span className="font-body opacity-75">· {tone.label}</span>}
    </span>
  );
}