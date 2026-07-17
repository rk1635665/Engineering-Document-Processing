import { STATUS_TONES } from "../data/badgeConfig";

export default function StatusBadge({ status }) {
  const tone = STATUS_TONES[status] ?? STATUS_TONES.queued;

  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
        tone.text,
        tone.bg,
      ].join(" ")}
    >
      <span className={["h-1.5 w-1.5 rounded-full", tone.dot].join(" ")} />
      {tone.label}
    </span>
  );
}