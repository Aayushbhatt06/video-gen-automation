import React, { useRef, useState } from "react";
import {
  X,
  Youtube,
  Key,
  CalendarClock,
  Upload,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";

export default function SettingsModal({
  open,
  onClose,
  health,
  onSaveSettings,
  onUploadClientSecret,
  onConnectYoutube,
  onDisconnectYoutube,
}) {
  if (!open) return null;

  const cfg = health?.automation?.config || {};
  const yt = health?.youtube || {};

  const [dailySlots, setDailySlots] = useState(
    (cfg.daily_slots || ["12:00", "15:00", "18:00", "21:00"]).join(", ")
  );
  const [timezone, setTimezone] = useState(cfg.timezone || "Asia/Kolkata");
  const [maxDaysAhead, setMaxDaysAhead] = useState(cfg.max_days_ahead ?? 7);
  const [maxUploadsPerDay, setMaxUploadsPerDay] = useState(cfg.max_uploads_per_day ?? 5);
  const [groqKey, setGroqKey] = useState("");
  const [geminiKey, setGeminiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [connectingYt, setConnectingYt] = useState(false);
  const secretInputRef = useRef(null);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const slotsList = dailySlots
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      await onSaveSettings({
        daily_slots: slotsList,
        timezone,
        max_days_ahead: Number(maxDaysAhead),
        max_uploads_per_day: Number(maxUploadsPerDay),
        ...(groqKey.trim() ? { groq_api_key: groqKey.trim() } : {}),
        ...(geminiKey.trim() ? { gemini_api_key: geminiKey.trim() } : {}),
      });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const handleSecretUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await onUploadClientSecret(file);
    e.target.value = "";
  };

  const handleOAuthConnect = async () => {
    setConnectingYt(true);
    try {
      await onConnectYoutube();
    } finally {
      setConnectingYt(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 space-y-5 shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="text-base font-bold text-white">
            Studio Settings — YouTube Channel &amp; Multi-Day Scheduler
          </h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* YouTube Channel OAuth Integration */}
        <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-bold text-white">
              <Youtube className="w-4 h-4 text-rose-500" />
              <span>YouTube Channel Integration (OAuth 2.0)</span>
            </div>
            {yt.connected ? (
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-0.5 rounded-full">
                <CheckCircle2 className="w-3 h-3" />
                Connected: {yt.channel?.title}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-300 bg-amber-500/10 border border-amber-500/30 px-2.5 py-0.5 rounded-full">
                <AlertCircle className="w-3 h-3" />
                Not Connected
              </span>
            )}
          </div>

          <p className="text-[11px] text-slate-400 leading-relaxed">
            {yt.message}
          </p>

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <input
              ref={secretInputRef}
              type="file"
              accept=".json"
              onChange={handleSecretUpload}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => secretInputRef.current?.click()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition"
            >
              <Upload className="w-3.5 h-3.5" />
              {yt.has_client_secret
                ? "Replace client_secret.json"
                : "Upload client_secret.json"}
            </button>

            {yt.has_client_secret && (
              <button
                type="button"
                onClick={handleOAuthConnect}
                disabled={connectingYt}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold transition disabled:opacity-50"
              >
                {connectingYt ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Authorizing in Browser...
                  </>
                ) : (
                  <>
                    <Youtube className="w-3.5 h-3.5" />
                    {yt.connected ? "Reconnect Channel" : "Connect YouTube Channel"}
                  </>
                )}
              </button>
            )}

            {yt.connected && (
              <button
                type="button"
                onClick={onDisconnectYoutube}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-rose-950 text-slate-300 hover:text-rose-300 text-xs transition"
              >
                Disconnect
              </button>
            )}
          </div>
        </div>

        {/* Multi-Day Slot Scheduler Settings */}
        <form onSubmit={handleSave} className="space-y-4">
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-bold text-white">
              <CalendarClock className="w-4 h-4 text-indigo-400" />
              <span>Multi-Day Daily Time Slots (24h format)</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">
                  Daily Slots (12pm, 3pm, 6pm, 9pm)
                </label>
                <input
                  type="text"
                  value={dailySlots}
                  onChange={(e) => setDailySlots(e.target.value)}
                  placeholder="12:00, 15:00, 18:00, 21:00"
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
                />
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">
                  Timezone
                </label>
                <input
                  type="text"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  placeholder="Asia/Kolkata"
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
                />
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">
                  Max Days Ahead Runway
                </label>
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={maxDaysAhead}
                  onChange={(e) => setMaxDaysAhead(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
                />
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">
                  Max YouTube Uploads / Day (Quota Guard)
                </label>
                <input
                  type="number"
                  min={1}
                  max={15}
                  value={maxUploadsPerDay}
                  onChange={(e) => setMaxUploadsPerDay(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
                />
              </div>
            </div>
          </div>

          {/* LLM API Keys */}
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-bold text-white">
              <Key className="w-4 h-4 text-amber-400" />
              <span>LLM Provider API Keys (.env)</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">
                  Groq API Key ({health?.providers?.groq_configured ? "Configured ✓" : "Not set"})
                </label>
                <input
                  type="password"
                  value={groqKey}
                  onChange={(e) => setGroqKey(e.target.value)}
                  placeholder="gsk_... (leave blank to keep current)"
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
                />
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">
                  Google Gemini API Key ({health?.providers?.gemini_configured ? "Configured ✓" : "Not set"})
                </label>
                <input
                  type="password"
                  value={geminiKey}
                  onChange={(e) => setGeminiKey(e.target.value)}
                  placeholder="AIza... (leave blank to keep current)"
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold"
            >
              {saving ? "Saving..." : "Save Configuration"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
