import React from "react";
import {
  Film,
  Download,
  Youtube,
  Loader2,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import BackgroundPicker from "./BackgroundPicker.jsx";

export default function PhonePreview({
  script,
  backgrounds,
  onUpdateScript,
  onUploadBackground,
  onRender,
  onScheduleYoutube,
  rendering,
  uploadingYt,
}) {
  const hasVideo = Boolean(script?.video_url);
  const selectedBg =
    backgrounds.find((c) => c.filename === script?.background_clip) ||
    backgrounds[0];

  return (
    <aside className="w-96 shrink-0 bg-slate-900/60 border-l border-slate-800 flex flex-col h-full overflow-y-auto p-4 space-y-4">
      {/* 9:16 Vertical Phone Frame */}
      <div className="flex flex-col items-center">
        <div className="w-60 aspect-[9/16] rounded-3xl bg-slate-950 border-2 border-slate-800 shadow-2xl overflow-hidden relative flex flex-col justify-between">
          {hasVideo ? (
            <video
              key={script.video_url}
              src={`${script.video_url}?t=${encodeURIComponent(script.updated_at || "")}`}
              controls
              playsInline
              className="w-full h-full object-cover"
            />
          ) : selectedBg?.video_url ? (
            <>
              <video
                key={selectedBg.video_url}
                src={selectedBg.video_url}
                autoPlay
                loop
                muted
                playsInline
                className="w-full h-full object-cover opacity-75"
              />
              {/* Safe-Zone Hormozi Caption Preview Overlay */}
              <div className="absolute inset-0 bg-gradient-to-b from-black/25 via-transparent to-black/75 pointer-events-none flex flex-col justify-end p-4 pb-16">
                <div className="text-center">
                  <span className="inline-block px-2 py-0.5 bg-black/70 text-yellow-300 font-black text-sm tracking-wide uppercase rounded shadow">
                    {(script?.beats?.[0]?.spoken_text || "STORY HOOK PREVIEW")
                      .split(/\s+/)
                      .slice(0, 3)
                      .join(" ")}
                  </span>
                </div>
                <p className="text-[10px] text-slate-300/80 text-center mt-2">
                  9:16 Safe-Zone Preview ({selectedBg.filename})
                </p>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-4 text-center text-xs text-slate-500">
              <Film className="w-8 h-8 mb-2 text-slate-600" />
              <span>9:16 Gameplay Preview</span>
            </div>
          )}
        </div>
      </div>

      {/* Render & Schedule CTAs */}
      {script && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => onRender(false)}
              disabled={rendering || script.status === "rendering"}
              className="flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition disabled:opacity-50"
            >
              {rendering || script.status === "rendering" ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Rendering...
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  Render Short
                </>
              )}
            </button>

            <button
              onClick={() => onRender(true)}
              disabled={rendering || script.status === "rendering"}
              title="Render and immediately upload as Unlisted into the next 12PM/3PM/6PM/9PM slot"
              className="flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold transition disabled:opacity-50"
            >
              <Youtube className="w-3.5 h-3.5" />
              Render + Schedule
            </button>
          </div>

          {hasVideo && (
            <div className="flex items-center gap-2">
              <button
                onClick={onScheduleYoutube}
                disabled={uploadingYt}
                className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-semibold transition disabled:opacity-50"
              >
                {uploadingYt ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Uploading Unlisted...
                  </>
                ) : (
                  <>
                    <Youtube className="w-3.5 h-3.5" />
                    {script.scheduled_slot_display
                      ? `Scheduled (${script.scheduled_slot_display})`
                      : "Upload Unlisted & Schedule Slot"}
                  </>
                )}
              </button>

              <a
                href={script.video_url}
                download={`${script.id}.mp4`}
                className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
                title="Download MP4"
              >
                <Download className="w-4 h-4" />
              </a>
            </div>
          )}

          {script.qa_report && (
            <div
              className={`p-2.5 rounded-xl border text-[11px] flex items-center justify-between ${
                script.qa_report.passed
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                  : "bg-rose-500/10 border-rose-500/30 text-rose-300"
              }`}
            >
              <span className="flex items-center gap-1.5 font-semibold">
                <CheckCircle2 className="w-3.5 h-3.5" />
                QA Gate: {script.qa_report.passed ? "PASSED" : "FAILED"}
              </span>
              <span className="font-mono">
                {script.qa_report.checks?.resolution} ·{" "}
                {script.qa_report.checks?.duration_sec}s
              </span>
            </div>
          )}
        </div>
      )}

      {/* Background Clip Picker & Uploader */}
      <BackgroundPicker
        backgrounds={backgrounds}
        selectedClip={script?.background_clip || "random"}
        cropAlign={script?.crop_align || "center"}
        ttsEngine={script?.tts_engine || "qwen3"}
        onChangeClip={(clip) =>
          script && onUpdateScript({ ...script, background_clip: clip }, true)
        }
        onChangeCrop={(align) =>
          script && onUpdateScript({ ...script, crop_align: align }, true)
        }
        onChangeTts={(engine) =>
          script && onUpdateScript({ ...script, tts_engine: engine }, true)
        }
        onUpload={onUploadBackground}
      />
    </aside>
  );
}
