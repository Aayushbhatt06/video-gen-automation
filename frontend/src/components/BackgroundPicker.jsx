import React, { useRef, useState } from "react";
import { Upload, Shuffle, Video, Cpu } from "lucide-react";

export default function BackgroundPicker({
  backgrounds,
  selectedClip,
  cropAlign,
  ttsEngine,
  onChangeClip,
  onChangeCrop,
  onChangeTts,
  onUpload,
}) {
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await onUpload(file);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  return (
    <div className="bg-slate-950/70 border border-slate-800/90 rounded-xl p-3.5 space-y-3">
      {/* TTS Voice Engine Selector */}
      <div className="space-y-1">
        <label className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5">
          <Cpu className="w-3.5 h-3.5 text-indigo-400" />
          English Voice Engine
        </label>
        <div className="grid grid-cols-2 gap-1.5 bg-slate-900 p-1 rounded-lg border border-slate-800 text-xs">
          <button
            type="button"
            onClick={() => onChangeTts("qwen3")}
            className={`py-1.5 rounded-md font-medium transition ${
              ttsEngine === "qwen3"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Qwen3-TTS (Emotional GPU)
          </button>
          <button
            type="button"
            onClick={() => onChangeTts("edge")}
            className={`py-1.5 rounded-md font-medium transition ${
              ttsEngine === "edge"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Edge-TTS (Fast Draft)
          </button>
        </div>
      </div>

      {/* Gameplay Clip Header & Upload */}
      <div className="flex items-center justify-between pt-1">
        <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5">
          <Video className="w-3.5 h-3.5 text-indigo-400" />
          Gameplay Backgrounds ({backgrounds.length})
        </span>
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp4,.mov,.mkv,.webm"
          onChange={handleFileChange}
          className="hidden"
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium border border-slate-700 transition"
        >
          <Upload className="w-3 h-3" />
          {uploading ? "Uploading..." : "+ Add Clip"}
        </button>
      </div>

      {/* Clip Selector Grid */}
      <div className="grid grid-cols-2 gap-2 max-h-44 overflow-y-auto pr-1">
        <button
          type="button"
          onClick={() => onChangeClip("random")}
          className={`p-2.5 rounded-lg border text-left flex flex-col justify-between transition ${
            selectedClip === "random"
              ? "bg-indigo-950/60 border-indigo-500 text-white"
              : "bg-slate-900/70 border-slate-800 text-slate-300 hover:border-slate-700"
          }`}
        >
          <Shuffle className="w-4 h-4 text-indigo-400 mb-1" />
          <span className="text-xs font-semibold">Random Non-Repeating</span>
          <span className="text-[10px] text-slate-400">Auto-picks fresh slice</span>
        </button>

        {backgrounds.map((clip) => (
          <button
            type="button"
            key={clip.filename}
            onClick={() => onChangeClip(clip.filename)}
            className={`p-2 rounded-lg border text-left flex flex-col justify-between transition overflow-hidden ${
              selectedClip === clip.filename
                ? "bg-indigo-950/60 border-indigo-500 text-white"
                : "bg-slate-900/70 border-slate-800 text-slate-300 hover:border-slate-700"
            }`}
          >
            <div className="text-[11px] font-semibold truncate w-full">
              {clip.filename}
            </div>
            <div className="text-[10px] text-slate-400 font-mono mt-1">
              {Math.round(clip.duration_sec || 0)}s · {clip.size_mb}MB
            </div>
          </button>
        ))}
      </div>

      {/* 9:16 Smart Crop Alignment */}
      <div className="flex items-center justify-between text-[11px] pt-1">
        <span className="text-slate-400">9:16 Crop Focus:</span>
        <div className="flex gap-1">
          {["left", "center", "right"].map((align) => (
            <button
              type="button"
              key={align}
              onClick={() => onChangeCrop(align)}
              className={`px-2.5 py-0.5 rounded capitalize border ${
                cropAlign === align
                  ? "bg-indigo-600 text-white border-indigo-500"
                  : "bg-slate-900 text-slate-400 border-slate-800"
              }`}
            >
              {align}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
