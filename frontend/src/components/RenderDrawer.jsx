import React, { useEffect, useRef, useState } from "react";
import { Terminal, ChevronUp, ChevronDown } from "lucide-react";

export default function RenderDrawer({ logs }) {
  const [open, setOpen] = useState(false);
  const scrollRef = useRef(null);
  const latest = logs?.[logs.length - 1];

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, open]);

  return (
    <div className="bg-slate-950 border-t border-slate-800 text-xs">
      <div
        onClick={() => setOpen(!open)}
        className="px-4 py-2 flex items-center justify-between cursor-pointer hover:bg-slate-900/60 transition"
      >
        <div className="flex items-center gap-2 truncate">
          <Terminal className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
          <span className="font-semibold text-slate-300">Live Studio Pipeline Console:</span>
          <span className="text-slate-400 font-mono truncate">
            {latest ? `[${latest.time}] ${latest.message}` : "Ready."}
          </span>
        </div>
        <button className="text-slate-400 hover:text-white flex items-center gap-1">
          <span>{open ? "Hide Logs" : `Logs (${logs?.length || 0})`}</span>
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
        </button>
      </div>

      {open && (
        <div
          ref={scrollRef}
          className="h-44 overflow-y-auto px-4 py-2.5 bg-slate-950/95 border-t border-slate-900 font-mono text-[11px] space-y-1"
        >
          {(logs || []).map((entry, idx) => (
            <div key={idx} className="text-slate-300 leading-relaxed">
              <span className="text-slate-500 mr-2">[{entry.time}]</span>
              <span>{entry.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
