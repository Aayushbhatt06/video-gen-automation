import React, { useState } from "react";
import {
  Sparkles,
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  Save,
  Volume2,
  Youtube,
  Loader2,
  Wand2,
  Mic,
} from "lucide-react";

const SFX_OPTIONS = ["none", "whoosh", "pop", "ding", "vine_boom"];

export default function ScriptEditor({
  script,
  presets,
  activeLanguage = "en",
  onGenerate,
  onSaveScript,
  onRewriteBeat,
  generating,
}) {
  const [topic, setTopic] = useState("");
  const [preset, setPreset] = useState("Reddit / Storytime Twist");
  const [provider, setProvider] = useState("groq");
  const [voiceGender, setVoiceGender] = useState("male");
  const [rewritingBeatId, setRewritingBeatId] = useState(null);
  const [saving, setSaving] = useState(false);

  const handleCreate = async (e) => {
    e.preventDefault();
    await onGenerate({
      topic,
      preset,
      language: activeLanguage,
      provider,
      voice_gender: voiceGender,
    });
    setTopic("");
  };

  if (!script) {
    return (
      <div className="flex-1 flex flex-col p-6 overflow-y-auto">
        <div className="max-w-2xl mx-auto w-full bg-slate-900/80 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/20 text-indigo-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">
                {activeLanguage === "hi"
                  ? "Generate Hindi Voice Story (English Captions & Metadata)"
                  : "Generate Emotional English Story Script"}
              </h2>
              <p className="text-xs text-slate-400">
                Automatically deduplicated via <code>story_history.txt</code> with per-beat Qwen3-TTS emotional voice instructions & full YouTube Shorts metadata.
              </p>
            </div>
          </div>

          <form onSubmit={handleCreate} className="space-y-3.5">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Story Preset
              </label>
              <div className="flex flex-wrap gap-1.5">
                {(presets || []).map((p) => (
                  <button
                    type="button"
                    key={p}
                    onClick={() => setPreset(p)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
                      preset === p
                        ? "bg-indigo-600 text-white border-indigo-500"
                        : "bg-slate-950 text-slate-300 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Custom Story Premise (Leave blank for automatic non-repeating seed angle)
              </label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g., A night-shift air traffic controller who heard a flight that landed 12 years ago..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="flex items-center justify-between gap-3 pt-1">
              <div className="flex items-center gap-2">
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200"
                >
                  <option value="groq">Groq (Llama 3.3 70B / GPT-OSS)</option>
                  <option value="gemini">Google Gemini 3.8 Flash</option>
                </select>

                <select
                  value={voiceGender}
                  onChange={(e) => setVoiceGender(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200"
                >
                  <option value="male">Male Storyteller (Ryan)</option>
                  <option value="female">Female Storyteller (Serena)</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={generating}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition disabled:opacity-50"
              >
                {generating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Writing Story & Metadata...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Generate English Story
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  const beats = script.beats || [];
  const totalWords = beats.reduce(
    (acc, b) => acc + (b.spoken_text || "").split(/\s+/).filter(Boolean).length,
    0
  );
  const estSeconds = script.duration_sec
    ? Math.round(script.duration_sec)
    : Math.round(totalWords / 2.6);

  const updateBeatField = (idx, field, value) => {
    const nextBeats = beats.map((b, i) => (i === idx ? { ...b, [field]: value } : b));
    onSaveScript({ ...script, beats: nextBeats }, false);
  };

  const addBeat = () => {
    const nextId = beats.length + 1;
    const nextBeats = [
      ...beats,
      {
        beat_id: nextId,
        speaker_role: "narrator",
        voice_gender: "male",
        emotion_instruct: "Speak with rising curiosity and a natural conversational storytelling tone",
        spoken_text: "And that's when they opened the final folder...",
        sfx_cue: "none",
      },
    ];
    onSaveScript({ ...script, beats: nextBeats }, true);
  };

  const removeBeat = (idx) => {
    const nextBeats = beats
      .filter((_, i) => i !== idx)
      .map((b, i) => ({ ...b, beat_id: i + 1 }));
    onSaveScript({ ...script, beats: nextBeats }, true);
  };

  const moveBeat = (idx, dir) => {
    const target = idx + dir;
    if (target < 0 || target >= beats.length) return;
    const copy = [...beats];
    const temp = copy[idx];
    copy[idx] = copy[target];
    copy[target] = temp;
    const reindexed = copy.map((b, i) => ({ ...b, beat_id: i + 1 }));
    onSaveScript({ ...script, beats: reindexed }, true);
  };

  const updateYtMeta = (field, value) => {
    onSaveScript(
      {
        ...script,
        youtube_meta: {
          ...script.youtube_meta,
          [field]: value,
        },
      },
      false
    );
  };

  const handlePersist = async () => {
    setSaving(true);
    try {
      await onSaveScript(script, true);
    } finally {
      setSaving(false);
    }
  };

  const handleRewrite = async (beatId, isHook = false) => {
    setRewritingBeatId(beatId);
    try {
      await onRewriteBeat(script.id, beatId, {
        is_hook: isHook,
        instruction: isHook
          ? "Rewrite this opening 0-2s hook to start mid-tension with maximum emotional curiosity for Qwen3-TTS"
          : "Make this line more emotional, natural, and conversational for Qwen3-TTS storytelling",
      });
    } finally {
      setRewritingBeatId(null);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto p-5 space-y-5">
      {/* Quick Generator Bar */}
      <form
        onSubmit={handleCreate}
        className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 flex flex-wrap items-center gap-2.5"
      >
        <select
          value={preset}
          onChange={(e) => setPreset(e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 font-medium"
        >
          {(presets || []).map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>

        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="New topic or leave empty for fresh non-repeating seed story..."
          className="flex-1 min-w-[210px] bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
        />

        <button
          type="submit"
          disabled={generating}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition disabled:opacity-50"
        >
          {generating ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Sparkles className="w-3.5 h-3.5" />
          )}
          New Story
        </button>
      </form>

      {/* Script Header & Duration Meter */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/50 border border-slate-800/80 rounded-xl p-4">
        <div className="space-y-1 flex-1 min-w-[240px]">
          <input
            type="text"
            value={script.title}
            onChange={(e) => onSaveScript({ ...script, title: e.target.value }, false)}
            className="bg-transparent text-base font-bold text-white focus:outline-none focus:border-b border-indigo-500 w-full"
          />
          <p className="text-[11px] text-slate-400">
            Premise Registry: <span className="text-slate-300">{script.core_premise || script.topic}</span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div
            className={`px-3 py-1.5 rounded-lg border text-xs font-mono ${
              estSeconds > 58
                ? "bg-rose-500/15 border-rose-500/40 text-rose-300"
                : "bg-slate-950 border-slate-800 text-slate-300"
            }`}
          >
            {beats.length} Beats · {totalWords} Words · ~{estSeconds}s
          </div>

          <button
            onClick={handlePersist}
            disabled={saving}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-100 text-xs font-semibold border border-slate-700 transition"
          >
            <Save className="w-3.5 h-3.5" />
            {saving ? "Saving..." : "Save Edits"}
          </button>
        </div>
      </div>

      {/* Beats List with Qwen3-TTS Emotional Voice Directions */}
      <div className="space-y-3">
        {beats.map((b, idx) => (
          <div
            key={b.beat_id}
            className="bg-slate-900/75 border border-slate-800/90 rounded-xl p-3.5 space-y-2.5 hover:border-slate-700/80 transition"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span
                  className={`px-2 py-0.5 rounded-md text-[11px] font-bold ${
                    idx === 0
                      ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                      : "bg-slate-800 text-slate-300"
                  }`}
                >
                  {idx === 0 ? "BEAT 1 · 0-2s HOOK" : `BEAT ${b.beat_id}`}
                </span>

                <select
                  value={b.voice_gender}
                  onChange={(e) => updateBeatField(idx, "voice_gender", e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-md px-2 py-1 text-[11px] text-slate-300"
                >
                  <option value="male">Male (Ryan)</option>
                  <option value="female">Female (Serena)</option>
                </select>

                <select
                  value={b.sfx_cue}
                  onChange={(e) => updateBeatField(idx, "sfx_cue", e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-md px-2 py-1 text-[11px] text-slate-300"
                >
                  {SFX_OPTIONS.map((sfx) => (
                    <option key={sfx} value={sfx}>
                      SFX: {sfx}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => handleRewrite(b.beat_id, idx === 0)}
                  disabled={rewritingBeatId === b.beat_id}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 border border-indigo-500/30 text-[11px] font-medium transition"
                >
                  {rewritingBeatId === b.beat_id ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Wand2 className="w-3 h-3" />
                  )}
                  {idx === 0 ? "Regenerate Hook" : "AI Polish"}
                </button>

                <button
                  type="button"
                  onClick={() => moveBeat(idx, -1)}
                  disabled={idx === 0}
                  className="p-1 text-slate-500 hover:text-slate-300 disabled:opacity-30"
                >
                  <ArrowUp className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => moveBeat(idx, 1)}
                  disabled={idx === beats.length - 1}
                  className="p-1 text-slate-500 hover:text-slate-300 disabled:opacity-30"
                >
                  <ArrowDown className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => removeBeat(idx)}
                  className="p-1 text-slate-500 hover:text-rose-400"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Qwen3-TTS Emotional Voice Direction Input */}
            <div className="flex items-center gap-2 bg-slate-950/70 border border-slate-800/80 rounded-lg px-2.5 py-1.5">
              <Mic className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
              <span className="text-[11px] text-slate-400 shrink-0">Qwen3 Emotion:</span>
              <input
                type="text"
                value={b.emotion_instruct || ""}
                onChange={(e) => updateBeatField(idx, "emotion_instruct", e.target.value)}
                placeholder="e.g., Speak with urgent curiosity and a hushed storytelling tone"
                className="w-full bg-transparent text-[11px] text-indigo-200 focus:outline-none"
              />
            </div>

            {/* Spoken Line (Hindi or English) + English Burned Caption when Hindi */}
            {script.language === "hi" ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-[10px] font-semibold uppercase tracking-wider text-amber-300/90 mb-1">
                    Hindi Voiceover (Spoken)
                  </label>
                  <textarea
                    rows={2}
                    value={b.spoken_text}
                    onChange={(e) => updateBeatField(idx, "spoken_text", e.target.value)}
                    className="w-full bg-slate-950/90 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-100 leading-relaxed focus:outline-none focus:border-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold uppercase tracking-wider text-indigo-300/90 mb-1">
                    English Burned-In Caption
                  </label>
                  <textarea
                    rows={2}
                    value={b.en_subtitle || ""}
                    onChange={(e) => updateBeatField(idx, "en_subtitle", e.target.value)}
                    className="w-full bg-slate-950/90 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-100 leading-relaxed focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>
            ) : (
              <textarea
                rows={2}
                value={b.spoken_text}
                onChange={(e) => updateBeatField(idx, "spoken_text", e.target.value)}
                className="w-full bg-slate-950/90 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-100 leading-relaxed focus:outline-none focus:border-indigo-500"
              />
            )}
          </div>
        ))}

        <button
          type="button"
          onClick={addBeat}
          className="w-full py-2.5 rounded-xl border border-dashed border-slate-700 hover:border-indigo-500/60 text-xs text-slate-400 hover:text-indigo-300 flex items-center justify-center gap-1.5 transition"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Story Beat
        </button>
      </div>

      {/* Complete YouTube Shorts Metadata Packaging */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2 text-xs font-bold text-white">
          <Youtube className="w-4 h-4 text-rose-500" />
          <span>Auto-Generated YouTube Shorts Upload Packaging</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">
              YouTube Shorts Title (&lt;= 100 chars, includes #Shorts)
            </label>
            <input
              type="text"
              value={script.youtube_meta?.title || ""}
              onChange={(e) => updateYtMeta("title", e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
            />
          </div>

          <div>
            <label className="block text-[11px] text-slate-400 mb-1">
              Pinned Engagement Caption / Hook
            </label>
            <input
              type="text"
              value={script.youtube_meta?.caption || ""}
              onChange={(e) => updateYtMeta("caption", e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
            />
          </div>
        </div>

        <div>
          <label className="block text-[11px] text-slate-400 mb-1">
            YouTube Shorts Description & Hashtags
          </label>
          <textarea
            rows={3}
            value={script.youtube_meta?.description || ""}
            onChange={(e) => updateYtMeta("description", e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200"
          />
        </div>

        <div>
          <label className="block text-[11px] text-slate-400 mb-1">
            YouTube Search Tags (comma-separated)
          </label>
          <input
            type="text"
            value={(script.youtube_meta?.tags || []).join(", ")}
            onChange={(e) =>
              updateYtMeta(
                "tags",
                e.target.value
                  .split(",")
                  .map((t) => t.trim())
                  .filter(Boolean)
              )
            }
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200"
          />
        </div>
      </div>
    </div>
  );
}
