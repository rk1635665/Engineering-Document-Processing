import { FileImage } from "lucide-react";

const IMAGE_EXT = /\.(png|jpe?g|gif|webp|tiff?)$/i;
const PDF_EXT = /\.pdf$/i;

/**
 * Renders whatever's at fileUrl inline: <img> for images, <iframe> for
 * PDFs (browsers render these natively), or a placeholder icon for
 * formats with no browser-native preview (.dwg/.dxf/etc.).
 */
export default function FilePreview({ fileUrl, name, apiBaseUrl, scale = 1 }) {
  if (!fileUrl) {
    return <FileImage size={48} className="text-slate-300" strokeWidth={1} />;
  }

  const src = `${apiBaseUrl}${fileUrl}`;

  if (PDF_EXT.test(fileUrl)) {
    return (
      <iframe
        src={src}
        title={name || "document preview"}
        className="w-full h-full border-0 bg-white"
        style={{ transform: `scale(${scale})`, transformOrigin: "center" }}
      />
    );
  }

  if (IMAGE_EXT.test(fileUrl)) {
    return (
      <img
        src={src}
        alt={name}
        className="max-h-full max-w-full object-contain transition-transform duration-150"
        style={{ transform: `scale(${scale})` }}
      />
    );
  }

  return (
    <div className="flex flex-col items-center gap-2 text-slate-400">
      <FileImage size={48} strokeWidth={1} />
      <span className="text-xs">No inline preview available for this file type</span>
    </div>
  );
}
