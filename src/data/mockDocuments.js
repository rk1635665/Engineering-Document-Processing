// Mock data standing in for a documents API. Shapes mirror what the
// eventual backend response is expected to look like.

export const recentDocuments = [
  {
    id: "doc-1042",
    name: "PSV-500A_Nameplate.jpg",
    type: "Nameplate",
    revision: "Rev. 2",
    status: "completed",
  },
  {
    id: "doc-1041",
    name: "Unit-12_PID-0034.pdf",
    type: "P&ID",
    revision: "Rev. C",
    status: "processing",
  },
  {
    id: "doc-1040",
    name: "NORD-Drive_MX56.png",
    type: "Nameplate",
    revision: "Rev. 1",
    status: "review",
  },
  {
    id: "doc-1039",
    name: "Compressor-Skid_GA-Drawing.dwg",
    type: "General Arrangement",
    revision: "Rev. B",
    status: "completed",
  },
  {
    id: "doc-1038",
    name: "Unit-12_PID-0031.pdf",
    type: "P&ID",
    revision: "Rev. D",
    status: "failed",
  },
  {
    id: "doc-1037",
    name: "PT-220_Nameplate.jpg",
    type: "Nameplate",
    revision: "Rev. 1",
    status: "queued",
  },
];
