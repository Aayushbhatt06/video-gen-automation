import React, { useState } from "react";
import {
  FileText,
  Trash2,
  CheckCircle2,
  Clock,
  AlertCircle,
  Loader2,
  Youtube,
  Search,
} from "lucide-react";

const STATUS_BADGES = {
  draft: { label: "Draft", color: "bg-slate-800 text-slate-300 border-slate-700" },
  rendering: { label: "Rendering", color: "bg-indigo-500/20 text-indigo-300 border-indigo-500/40" },
  rendered: { label: "Rendered", color: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
  ready_to_upload: { label: "Ready for YT", color: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30" },
  scheduled_public: { label: "Scheduled on YT", color: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
  published: { label: "Public on YT", color: "bg-rose-500/20 text-rose-300 border-rose-500/40" },
  qa_failed: { label: "QA Failed", color: "bg-rose-500/20 text-rose-300 border-rose-500/40" },
  failed: { label: "Failed", color: "bg-rose-500/20 text-rose-300 border-rose-500/40" },
};

export default function ScriptSidebar({
  scripts,
  selectedId,
  onSelect,
  onDelete,
  storyHistoryCount,
}) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");

  const filtered = scripts.filter((s) => {
    if (filter === "draft" && s.status !== "draft") return false;
    if (filter === "rendered" && !["rendered", "ready_to_upload"].includes(s.status))
      return false;
    if (filter === "scheduled" && !["scheduled_public", "published"].includes(s.status))
      return false;
    if (query.trim()) {
      const q = query.toLowerCase();
      return (
        (s.title || "").toLowerCase().includes(q) ||
        (s.topic || "").toLowerCase().includes(q) ||
        (s.preset || "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <aside className="w-72 shrink-0 bg-slate-900/60 border-r border-slate-800 flex flex-col h-full">
      {/* Header & Deduplication Counter */}
      <div className="p-3.5 border-b border-slate-800 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            English Story Queue ({scripts.length})
          </span>
          <span
            className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/30"
            title="Stories tracked in data/story_history.txt to prevent repetition"
          >
            {storyHistoryCount} in Memory
          </span>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search stories..."
            className="w-full bg-slate-950/80 border border-slate-800 rounded-lg pl-8 pr-2.5 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        {/* Filter Tabs */}
        <div className="grid grid-cols-4 gap-1 bg-slate-950/90 p-1 rounded-lg border border-slate-800/80 text-[11px]">
          {[
            { id: "all", label: "All" },
            { id: "draft", label: "Draft" },
            { id: "rendered", label: "Ready" },
            { id: "scheduled", label: "YT Slot" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setFilter(t.id)}
              className={`py-1 rounded-md font-medium transition ${
                filter === t.id
                  ? "bg-indigo-600 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Script List */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2">
        {filtered.length === 0 ? (
          <div className="text-center py-12 px-4 text-xs text-slate-500">
            No English stories match this view. Click{" "}
            <strong className="text-slate-300">Generate Story</strong> or enable{" "}
            <strong className="text-emerald-400">Autonomous Automation</strong>.
          </div>
        ) : (
          filtered.map((item) => {
            const active = item.id === selectedId;
            const badge = STATUS_BADGES[item.status] || STATUS_BADGES.draft;
            const wordCount = (item.beats || []).reduce(
              (acc, b) => acc + (b.spoken_text || "").split(/\s+/).filter(Boolean).length,
              0
            );
            const estDur = item.duration_sec
              ? `${Math.round(item.duration_sec)}s`
              : `~${Math.round(wordCount / 2.6)}s`;

            return (
              <div
                key={item.id}
                onClick={() => onSelect(item.id)}
                className={`group relative rounded-xl p-3 border transition cursor-pointer ${
                  active
                    ? "bg-indigo-950/50 border-indigo-500/60 shadow-sm"
                    : "bg-slate-900/80 border-slate-800/80 hover:border-slate-700"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <h4 className="text-xs font-semibold text-slate-100 line-clamp-2 leading-snug">
                    {item.title || "Untitled Story"}
                  </h4>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(item.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 transition p-0.5"
                    title="Delete script"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                <p className="text-[11px] text-slate-400 truncate mt-1">
                  {item.preset}
                </p>

                <div className="flex items-center justify-between mt-2.5 pt-2 border-t border-slate-800/70 text-[11px]">
                  <span
                    className={`px-2 py-0.5 rounded-md border font-medium ${badge.color}`}
                  >
                    {badge.label}
                  </span>
                  <span className="text-slate-400 font-mono">{estDur}</span>
                </div>

                {item.scheduled_slot_display && (
                  <div className="mt-1.5 flex items-center gap-1 text-[10px] text-amber-300/90 font-medium">
                    <Youtube className="w-3 h-3 shrink-0" />
                    <span className="truncate">Slot: {item.scheduled_slot_display}</span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
