// Mock data for revision comparison — stands in for a real diffing
// service that would compare two parsed drawing revisions.

export const revisionOptions = ["Rev. A", "Rev. B", "Rev. C", "Rev. D"];

export const differenceSummary = [
  {
    id: "diff-1",
    attribute: "PSV-500A Tolerance",
    revisionA: "±0.10 mm",
    revisionB: "±0.05 mm",
    status: "modified",
  },
  {
    id: "diff-2",
    attribute: "Flange 3in Material",
    revisionA: "A105",
    revisionB: "SA-516 Gr. 70",
    status: "modified",
  },
  {
    id: "diff-3",
    attribute: "Instrument Tag PIC-2210",
    revisionA: "—",
    revisionB: "PIC-2210",
    status: "added",
  },
  {
    id: "diff-4",
    attribute: "Instrument Tag TIC-1098",
    revisionA: "TIC-1098",
    revisionB: "—",
    status: "removed",
  },
  {
    id: "diff-5",
    attribute: "Line Size FT-0034",
    revisionA: "2 in Sch. 40",
    revisionB: "3 in Sch. 40",
    status: "modified",
  },
  {
    id: "diff-6",
    attribute: "Relief Valve Setpoint Note",
    revisionA: "—",
    revisionB: "Set at 150 psig, see Note 4",
    status: "added",
  },
];

// Highlight regions overlaid on the mock drawing preview. Coordinates are
// percentages of the viewer's viewBox so both panels can share one layout.
export const highlightRegions = {
  revisionA: [
    { id: "h1", x: 58, y: 18, w: 26, h: 14, type: "modified", label: "Tolerance block" },
    { id: "h2", x: 12, y: 60, w: 22, h: 12, type: "removed", label: "TIC-1098" },
  ],
  revisionB: [
    { id: "h1", x: 58, y: 18, w: 26, h: 14, type: "modified", label: "Tolerance block" },
    { id: "h3", x: 42, y: 60, w: 22, h: 12, type: "added", label: "PIC-2210" },
    { id: "h4", x: 12, y: 78, w: 30, h: 10, type: "added", label: "Setpoint note" },
  ],
};

export const suggestedQuestions = [
  "What changed?",
  "Show tolerance changes.",
  "Material differences.",
];

// Canned assistant replies keyed by intent — matched with simple keyword
// checks in the page component. Purely a UI mock, no model call.
export const mockAssistantReplies = {
  changed:
    "Between Rev. A and Rev. B: 3 attributes were modified, 2 instrument tags were added, and 1 tag was removed. The tolerance block and the FT-0034 line size both tightened.",
  tolerance:
    "PSV-500A tolerance moved from ±0.10 mm to ±0.05 mm — a tighter spec in Rev. B. No other tolerance values changed between these two revisions.",
  material:
    "The 3 in flange material changed from A105 to SA-516 Gr. 70 in Rev. B. All other material callouts are unchanged.",
  fallback:
    "I can answer questions about what changed, tolerance updates, or material differences between the two selected revisions — try one of the suggestions above.",
};
