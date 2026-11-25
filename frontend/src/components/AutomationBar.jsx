import React from "react";
import {
  Play,
  Square,
  Zap,
  CalendarClock,
  ShieldCheck,
  Loader2,
  AlertTriangle,
  ListOrdered,
} from "lucide-react";

const PHASE_LABELS = {
  idle: "Idle & Ready",
  generating_story: "Writing Unique Story...",
  rendering_video: "Rendering Short...",
  uploading_youtube: "Uploading & Scheduling on YouTube...",
  waiting_queue: "Processing Queued Render...",
  cooldown: "Cooling Down Before Next Story...",
  waiting_daily_quota: "Daily Upload Cap Reached",
  runway_full: "Multi-Day Schedule Runway Full",
  stopping: "Finishing Current Step & Stopping...",
};

export default function AutomationBar({
  automation,
  onStart,
  onStop,
  onRunOnce,
  busy,
}) {
  const isActive = Boolean(automation?.active);
  const phase = automation?.phase || "idle";
  const isWorking =
    phase === "generating_story" ||
    phase === "rendering_video" ||
    phase === "uploading_youtube" ||
    phase === "waiting_queue" ||
    phase === "cooldown";
  const pct = automation?.progress_pct ?? 0;
  const stage = automation?.progress_stage || PHASE_LABELS[phase] || phase;
  const queuedCount = (automation?.queued_renders || []).length;
  const nextSlot = automation?.next_free_slot;
  const uploadsToday = automation?.uploads_today ?? 0;
  const maxDaily = automation?.max_uploads_per_day ?? 5;

  return (
    <div className="bg-slate-900/90 border-b border-slate-800 px-5 py-2.5 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Left: Master Automation Toggle & Live Phase */}
        <div className="flex items-center gap-3">
          <button
            onClick={isActive ? onStop : onStart}
            disabled={busy}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-sm ${
              isActive
                ? "bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30"
                : "bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold"
            }`}
          >
            {isActive ? (
              <>
                <Square className="w-3.5 h-3.5 fill-current" />
                Pause Autonomous Loop
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                Start Autonomous Automation
              </>
            )}
          </button>

          <button
            onClick={onRunOnce}
            disabled={busy || isActive || isWorking}
            title="Create, Render & Schedule 1 New English Short Right Now"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/25 disabled:opacity-40 transition"
          >
            <Zap className="w-3.5 h-3.5" />
            Create &amp; Schedule 1 Now
          </button>

          <div className="flex items-center gap-2 pl-2 border-l border-slate-800 text-xs">
            {isWorking || isActive ? (
              <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin shrink-0" />
            ) : (
              <span className="w-2 h-2 rounded-full bg-slate-500 shrink-0" />
            )}
            <span className="text-slate-300 font-medium">
              {isWorking ? stage : PHASE_LABELS[phase] || phase}
            </span>
          </div>
        </div>

        {/* Right: Queue, Multi-Day Slot & Quota Telemetry */}
        <div className="flex items-center gap-2.5 text-xs">
          {queuedCount > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 font-semibold">
              <ListOrdered className="w-3.5 h-3.5" />
              <span>{queuedCount} Queued in Pipeline</span>
            </div>
          )}

          {automation?.last_error && (
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 max-w-xs truncate"
              title={automation.last_error}
            >
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{automation.last_error}</span>
            </div>
          )}

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800/80 border border-slate-700/70 text-slate-300">
            <CalendarClock className="w-3.5 h-3.5 text-indigo-400" />
            <span>Next Slot:</span>
            <span className="font-semibold text-white">
              {nextSlot ? nextSlot.slot_local_display : "Runway Full"}
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800/80 border border-slate-700/70 text-slate-300">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Daily YT Quota:</span>
            <span className="font-semibold text-white">
              {uploadsToday} / {maxDaily}
            </span>
          </div>
        </div>
      </div>

      {/* Live Progress Bar with Percentage when active */}
      {(isWorking || pct > 0) && (
        <div className="flex items-center gap-3">
          <div className="flex-1 h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 transition-all duration-500 ease-out"
              style={{ width: `${Math.max(4, pct)}%` }}
            />
          </div>
          <span className="text-[11px] font-mono font-bold text-indigo-300 w-10 text-right">
            {pct}%
          </span>
        </div>
      )}
    </div>
  );
}
