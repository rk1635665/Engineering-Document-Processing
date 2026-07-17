import { useState } from "react";
import { Send, Sparkles } from "lucide-react";

export default function ChatColumn({ messages, onSendMessage, title = "AI Chat", placeholder = "Ask AI..." }) {
  const [draft, setDraft] = useState("");

  const handleSend = (e) => {
    e.preventDefault();
    if (!draft.trim()) return;
    onSendMessage(draft.trim());
    setDraft("");
  };

  return (
    <div className="flex flex-col h-full bg-paper">
      <div className="px-4 py-3 border-b border-line bg-white">
        <h2 className="font-display text-sm font-semibold text-ink">{title}</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
        {messages.map((m) => {
          const isUser = m.role === "user";
          return (
            <div key={m.id} className={isUser ? "flex justify-end" : "flex justify-start"}>
              <div
                className={[
                  "max-w-[90%] rounded-lg px-3 py-2 text-sm leading-relaxed",
                  isUser ? "bg-blue-500 text-white" : "bg-white border border-line text-ink"
                ].join(" ")}
              >
                {!isUser && (
                  <span className="mb-1 flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-blue-600">
                    <Sparkles size={10} /> Assistant
                  </span>
                )}
                {m.text}
              </div>
            </div>
          );
        })}
      </div>
      <div className="p-3 bg-white border-t border-line">
        <form onSubmit={handleSend} className="relative flex items-center">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={placeholder}
            className="w-full rounded-lg border border-line bg-paper pl-3 pr-10 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={!draft.trim()}
            className="absolute right-1 top-1 flex h-7 w-7 items-center justify-center rounded bg-blue-500 text-white disabled:opacity-40 transition-colors hover:bg-blue-600"
          >
            <Send size={14} />
          </button>
        </form>
      </div>
    </div>
  );
}