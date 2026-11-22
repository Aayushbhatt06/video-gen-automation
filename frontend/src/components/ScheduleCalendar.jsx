import React from "react";
import {
  Calendar,
  Clock,
  ExternalLink,
  RefreshCw,
  Globe,
  Lock,
  Trash2,
  CheckCircle2,
  Sparkles,
} from "lucide-react";

export default function ScheduleCalendar({
  scheduleData,
  onRefreshSlot,
  onPublishNow,
  onDeleteSlot,
  busySlotId,
}) {
  const scheduledSlots = scheduleData?.scheduled_slots || [];
  const upcomingFree = scheduleData?.upcoming_free_slots || [];
  const config = scheduleData?.config || {};

  return (
    <div className="flex-1 overflow-y-auto p-5 space-y-6">
      {/* Header Explanation */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Calendar className="w-4 h-4 text-indigo-400" />
            Multi-Day YouTube Shorts Schedule Board (Unlisted Processing &rarr; Public Slot)
          </h2>
          <p className="text-xs text-slate-400">
            Every Short uploads as <strong className="text-amber-300">Unlisted</strong> first so YouTube completes HD &amp; Shorts checks, then automatically flips to <strong className="text-emerald-300">Public</strong> on your daily slots:{" "}
            <code className="text-indigo-300">
              {(config.daily_slots || ["12:00", "15:00", "18:00", "21:00"]).join(" · ")}
            </code>{" "}
            ({config.timezone || "Asia/Kolkata"}).
          </p>
        </div>
      </div>

      {/* Active Scheduled & Published Slots */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Scheduled &amp; Deployed YouTube Shorts ({scheduledSlots.length})
        </h3>

        {scheduledSlots.length === 0 ? (
          <div className="bg-slate-900/50 border border-slate-800/80 rounded-xl p-8 text-center text-xs text-slate-400">
            No Shorts scheduled yet. Enable{" "}
            <strong className="text-emerald-400">Autonomous Automation</strong> or click{" "}
            <strong className="text-indigo-300">Create &amp; Schedule 1 Now</strong> to start building your multi-day runway.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {scheduledSlots.map((slot) => {
              const isPublic = slot.privacy_status === "public";
              const isBusy = busySlotId === slot.slot_id;

              return (
                <div
                  key={slot.slot_id}
                  className="bg-slate-900/85 border border-slate-800 rounded-xl p-4 flex flex-col justify-between gap-3"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-300 bg-indigo-500/15 border border-indigo-500/30 px-2.5 py-0.5 rounded-md">
                        <Clock className="w-3.5 h-3.5" />
                        {slot.slot_local_display}
                      </span>

                      <span
                        className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-md border ${
                          isPublic
                            ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                            : "bg-amber-500/15 text-amber-300 border-amber-500/30"
                        }`}
                      >
                        {isPublic ? (
                          <>
                            <Globe className="w-3 h-3" />
                            PUBLIC LIVE
                          </>
                        ) : (
                          <>
                            <Lock className="w-3 h-3" />
                            UNLISTED ({slot.processing_status || "processing"})
                          </>
                        )}
                      </span>
                    </div>

                    <h4 className="text-xs font-semibold text-white line-clamp-1">
                      {slot.script_title}
                    </h4>

                    {slot.youtube_url && (
                      <a
                        href={slot.youtube_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] text-indigo-400 hover:text-indigo-300"
                      >
                        <span>{slot.youtube_url}</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
                    <div className="flex items-center gap-1.5">
                      {slot.youtube_video_id && !isPublic && (
                        <>
                          <button
                            onClick={() => onRefreshSlot(slot.slot_id)}
                            disabled={isBusy}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] transition"
                          >
                            <RefreshCw className={`w-3 h-3 ${isBusy ? "animate-spin" : ""}`} />
                            Check HD Status
                          </button>
                          <button
                            onClick={() => onPublishNow(slot.slot_id)}
                            disabled={isBusy}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 text-[11px] font-medium transition"
                          >
                            <CheckCircle2 className="w-3 h-3" />
                            Flip Public Now
                          </button>
                        </>
                      )}
                    </div>

                    <button
                      onClick={() => onDeleteSlot(slot.slot_id)}
                      className="p-1 text-slate-500 hover:text-rose-400 transition"
                      title="Remove from schedule state"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Upcoming Free Multi-Day Runway Slots */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Next Available Multi-Day Time Slots (12 PM · 3 PM · 6 PM · 9 PM &rarr; Next Day)
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
          {upcomingFree.map((free, i) => (
            <div
              key={free.slot_iso}
              className="bg-slate-900/40 border border-dashed border-slate-800 rounded-xl p-3 space-y-1"
            >
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>Slot #{i + 1}</span>
                <Sparkles className="w-3 h-3 text-indigo-400" />
              </div>
              <p className="text-xs font-bold text-slate-200">{free.time_label}</p>
              <p className="text-[11px] text-slate-400">{free.date_label}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
