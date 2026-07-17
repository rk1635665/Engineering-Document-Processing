// Mock data for a single document awaiting human review — stands in for
// a real record fetched by document ID.

export const reviewDocument = {
  name: "PSV-500A_Nameplate.jpg",
  type: "Nameplate",
  revision: "Rev. 2",
  uploadedAt: "Jul 8, 2026",
  pageCount: 1,
};

export const initialFields = [
  { id: "f1", label: "Part Number", value: "PSV-500A", confidence: 97 },
  { id: "f2", label: "Manufacturer", value: "Anderson Greenwood", confidence: 92 },
  { id: "f3", label: "Material", value: "SA-516 Gr. 70", confidence: 89 },
  { id: "f4", label: "Set Pressure", value: "150 psig", confidence: 95 },
  { id: "f5", label: "Orifice Size", value: "\"D\"", confidence: 61 },
  { id: "f6", label: "Tolerance", value: "±0.05 mm", confidence: 74 },
  { id: "f7", label: "Serial Number", value: "SN-88214-C", confidence: 58 },
];

export const suggestedQuestions = [
  "Is extraction correct?",
  "Why confidence is low?",
  "Explain this value.",
];

// Canned assistant replies keyed by intent — matched with simple keyword
// checks in the page component. Purely a UI mock, no model call.
export const mockAssistantReplies = {
  correct:
    "Most fields look consistent with a typical PSV nameplate. Orifice Size and Serial Number are below 70% confidence, so I'd double check those two against the original photo before approving.",
  confidence:
    "Low confidence usually comes from glare, a worn or scratched tag surface, or small stamped characters that OCR struggles to separate — that's the case for Orifice Size and Serial Number here.",
  explain:
    "The Orifice Size field reads as a single letter designation (e.g. \"D\"), which is standard PSV sizing shorthand — but the stamped character is faint in this photo, which is why confidence sits at 61%.",
  fallback:
    "I can help you sanity-check this extraction, explain a low-confidence field, or clarify what a specific value means — try one of the suggestions above.",
};
