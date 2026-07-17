import { useState } from "react";
import { MessageCircle, X } from "lucide-react";
import ChatColumn from "./ChatColumn";

export default function FloatingChat({ messages, onSendMessage }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {open && (
        <div className="fixed bottom-24 right-6 z-50 w-96 h-[32rem] border border-line rounded-xl overflow-hidden bg-white shadow-2xl flex flex-col">
          <div className="flex items-center justify-between px-4 py-2 border-b border-line bg-white">
            <span className="text-sm font-medium text-ink">AI Chat</span>
            <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-ink">
              <X size={16} />
            </button>
          </div>
          <div className="flex-1 min-h-0 flex flex-col">
            <ChatColumn messages={messages} onSendMessage={onSendMessage} />
          </div>
        </div>
      )}
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Toggle AI Chat"
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-blue-500 text-white shadow-lg hover:bg-blue-600 transition-colors"
      >
        <MessageCircle size={22} />
      </button>
    </>
  );
}