import React, { useEffect, useState } from "react";
import {
  Sparkles,
  Settings,
  Youtube,
  Calendar,
  FileEdit,
  PlusCircle,
  Languages,
} from "lucide-react";
import { api } from "./api/client.js";
import AutomationBar from "./components/AutomationBar.jsx";
import ScriptSidebar from "./components/ScriptSidebar.jsx";
import ScriptEditor from "./components/ScriptEditor.jsx";
import ScheduleCalendar from "./components/ScheduleCalendar.jsx";
import PhonePreview from "./components/PhonePreview.jsx";
import RenderDrawer from "./components/RenderDrawer.jsx";
import SettingsModal from "./components/SettingsModal.jsx";

export default function App() {
  const [health, setHealth] = useState(null);
  const [scripts, setScripts] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [backgrounds, setBackgrounds] = useState([]);
  const [voicesData, setVoicesData] = useState(null);
  const [scheduleData, setScheduleData] = useState(null);
  const [activeTab, setActiveTab] = useState("studio"); // "studio" | "schedule"
  const [settingsOpen, setSettingsOpen] = useState(false);

  const [generating, setGenerating] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [uploadingYt, setUploadingYt] = useState(false);
  const [automationBusy, setAutomationBusy] = useState(false);
  const [busySlotId, setBusySlotId] = useState(null);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4500);
  };

  const refreshAll = async () => {
    try {
      const [h, scList, bgRes, schedRes, vRes] = await Promise.all([
        api.getHealth(),
        api.listScripts(),
        api.listBackgrounds(),
        api.getSchedule(),
        api.listVoices(),
      ]);
      setHealth(h);
      setScripts(scList);
      setBackgrounds(bgRes.clips || []);
      setScheduleData(schedRes);
      setVoicesData(vRes);

      if (!selectedId && scList.length > 0) {
        setSelectedId(scList[0].id);
      }
    } catch (e) {
      console.error("Failed to fetch studio state:", e);
    }
  };

  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshAll, 1500);
    const handleToggleLanguage = async (nextLang) => {
    try {
      await api.updateSettings({ default_language: nextLang });
      await refreshAll();
      showToast(
        nextLang === "hi"
          ? "Switched to Hindi Voiceover (Captions, Title, Description & Tags stay English)"
          : "Switched to English-only mode",
        "success"
      );
    } catch (e) {
      showToast(`Language switch failed: ${e.message}`, "error");
    }
  };

  const activeLanguage = health?.language || "en";

  return () => clearInterval(interval);
  }, []);

  const selectedScript = scripts.find((s) => s.id === selectedId) || null;

  const handleGenerateScript = async (payload) => {
    setGenerating(true);
    try {
      const created = await api.generateScript(payload);
      await refreshAll();
      setSelectedId(created.id);
      setActiveTab("studio");
      showToast(`Generated unique story: "${created.title}"`, "success");
    } catch (e) {
      showToast(`Story generation failed: ${e.message}`, "error");
    } finally {
      setGenerating(false);
    }
  };

  const handleSaveScript = async (updated, persistRemote = true) => {
    setScripts((prev) =>
      prev.map((s) => (s.id === updated.id ? updated : s))
    );
    if (persistRemote) {
      try {
        await api.updateScript(updated.id, updated);
        showToast("Saved script & metadata", "success");
      } catch (e) {
        showToast(`Save failed: ${e.message}`, "error");
      }
    }
  };

  const handleRewriteBeat = async (scriptId, beatId, payload) => {
    try {
      const updated = await api.rewriteBeat(scriptId, beatId, payload);
      setScripts((prev) =>
        prev.map((s) => (s.id === updated.id ? updated : s))
      );
      showToast(`Polished Beat #${beatId} for Qwen3-TTS`, "success");
    } catch (e) {
      showToast(`Beat rewrite failed: ${e.message}`, "error");
    }
  };

  const handleDeleteScript = async (id) => {
    try {
      await api.deleteScript(id);
      const next = scripts.filter((s) => s.id !== id);
      setScripts(next);
      if (selectedId === id) {
        setSelectedId(next[0]?.id || null);
      }
    } catch (e) {
      showToast(`Delete failed: ${e.message}`, "error");
    }
  };

  const handleRender = async (autoUploadYoutube = false) => {
    if (!selectedScript) return;
    setRendering(true);
    try {
      await api.updateScript(selectedScript.id, selectedScript);
      await api.renderScript(selectedScript.id, {
        tts_engine: selectedScript.tts_engine,
        background_clip: selectedScript.background_clip,
        crop_align: selectedScript.crop_align,
        auto_upload_youtube: autoUploadYoutube,
      });
      showToast(
        autoUploadYoutube
          ? "Rendering started -> will auto-upload Unlisted & schedule into next slot!"
          : "Rendering started in background...",
        "success"
      );
      await refreshAll();
    } catch (e) {
      showToast(`Render failed: ${e.message}`, "error");
    } finally {
      setRendering(false);
    }
  };

  const handleScheduleYoutube = async () => {
    if (!selectedScript) return;
    setUploadingYt(true);
    try {
      const res = await api.scheduleYoutubeUpload(selectedScript.id);
      await refreshAll();
      showToast(
        `Uploaded as UNLISTED & scheduled for ${res.slot?.slot_local_display}!`,
        "success"
      );
    } catch (e) {
      showToast(`YouTube upload failed: ${e.message}`, "error");
    } finally {
      setUploadingYt(false);
    }
  };

  const handleStartAutomation = async () => {
    setAutomationBusy(true);
    try {
      await api.startAutomation();
      await refreshAll();
      showToast("Autonomous story creation & multi-day YouTube scheduler activated!", "success");
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      setAutomationBusy(false);
    }
  };

  const handleStopAutomation = async () => {
    setAutomationBusy(true);
    try {
      await api.stopAutomation();
      await refreshAll();
      showToast("Autonomous loop paused.", "info");
    } finally {
      setAutomationBusy(false);
    }
  };

  const handleRunOnce = async () => {
    setAutomationBusy(true);
    try {
      await api.runAutomationOnce();
      await refreshAll();
      showToast("Triggered 1 autonomous story -> render -> unlisted schedule cycle!", "success");
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      setAutomationBusy(false);
    }
  };

  const handleToggleLanguage = async (nextLang) => {
    try {
      await api.updateSettings({ default_language: nextLang });
      await refreshAll();
      showToast(
        nextLang === "hi"
          ? "Switched to Hindi Voiceover (Captions, Title, Description & Tags stay English)"
          : "Switched to English-only mode",
        "success"
      );
    } catch (e) {
      showToast(`Language switch failed: ${e.message}`, "error");
    }
  };

  const activeLanguage = health?.language || "en";

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-slate-950 text-slate-100">
      {/* Top Studio Bar */}
      <header className="h-14 shrink-0 bg-slate-900 border-b border-slate-800 px-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-tight">
              Faceless Shorts Studio <span className="text-indigo-400">v2</span>
            </h1>
            <p className="text-[11px] text-slate-400">
              English Emotional Qwen3-TTS · Unlisted Processing &rarr; Multi-Day YouTube Scheduler
            </p>
          </div>
        </div>

        {/* Center Workspace Mode Switcher */}
        <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab("studio")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === "studio"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <FileEdit className="w-3.5 h-3.5" />
            Story &amp; Beat Studio
          </button>
          <button
            onClick={() => setActiveTab("schedule")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === "schedule"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Calendar className="w-3.5 h-3.5" />
            YouTube Schedule Board (12PM / 3PM / 6PM / 9PM)
          </button>
        </div>

        {/* Right Status, Language Switch & Settings */}
        <div className="flex items-center gap-2.5">
          {/* English <-> Hindi Voice Switch */}
          <div
            className="flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs"
            title="Switch Voiceover Language (Captions, Title & Description always stay English)"
          >
            <Languages className="w-3.5 h-3.5 text-indigo-400 mx-1.5" />
            <button
              onClick={() => handleToggleLanguage("en")}
              className={`px-2.5 py-1 rounded-md font-semibold transition ${
                activeLanguage === "en"
                  ? "bg-indigo-600 text-white"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              EN
            </button>
            <button
              onClick={() => handleToggleLanguage("hi")}
              className={`px-2.5 py-1 rounded-md font-semibold transition ${
                activeLanguage === "hi"
                  ? "bg-amber-500 text-slate-950"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              हिंदी (EN Cap)
            </button>
          </div>

          <button
            onClick={() => setSettingsOpen(true)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
              health?.youtube?.connected
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                : "bg-amber-500/10 border-amber-500/30 text-amber-300"
            }`}
          >
            <Youtube className="w-3.5 h-3.5" />
            {health?.youtube?.connected
              ? health.youtube.channel?.title || "YT Connected"
              : "Connect YouTube"}
          </button>

          <button
            onClick={() => {
              setSelectedId(null);
              setActiveTab("studio");
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            New Story
          </button>

          <button
            onClick={() => setSettingsOpen(true)}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            title="Studio & YouTube Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Autonomous Automation Control Bar */}
      <AutomationBar
        automation={health?.automation}
        onStart={handleStartAutomation}
        onStop={handleStopAutomation}
        onRunOnce={handleRunOnce}
        busy={automationBusy}
      />

      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed bottom-12 right-6 z-50 px-4 py-2.5 rounded-xl shadow-xl border text-xs font-semibold ${
            toast.type === "error"
              ? "bg-rose-950/95 border-rose-500/50 text-rose-200"
              : "bg-indigo-950/95 border-indigo-500/50 text-indigo-100"
          }`}
        >
          {toast.msg}
        </div>
      )}

      {/* Main 3-Zone Workspace */}
      <div className="flex-1 flex overflow-hidden">
        <ScriptSidebar
          scripts={scripts}
          selectedId={selectedId}
          onSelect={(id) => {
            setSelectedId(id);
            setActiveTab("studio");
          }}
          onDelete={handleDeleteScript}
          storyHistoryCount={health?.story_history_count ?? 0}
        />

        {activeTab === "schedule" ? (
          <ScheduleCalendar
            scheduleData={scheduleData}
            busySlotId={busySlotId}
            onRefreshSlot={async (slotId) => {
              setBusySlotId(slotId);
              try {
                await api.refreshSlotStatus(slotId);
                await refreshAll();
              } catch (e) {
                showToast(e.message, "error");
              } finally {
                setBusySlotId(null);
              }
            }}
            onPublishNow={async (slotId) => {
              setBusySlotId(slotId);
              try {
                await api.publishSlotNow(slotId);
                await refreshAll();
                showToast("Promoted Short from Unlisted -> PUBLIC!", "success");
              } catch (e) {
                showToast(e.message, "error");
              } finally {
                setBusySlotId(null);
              }
            }}
            onDeleteSlot={async (slotId) => {
              await api.deleteScheduleSlot(slotId);
              await refreshAll();
            }}
          />
        ) : (
          <ScriptEditor
            script={selectedScript}
            presets={health?.presets}
            activeLanguage={activeLanguage}
            onGenerate={handleGenerateScript}
            onSaveScript={handleSaveScript}
            onRewriteBeat={handleRewriteBeat}
            generating={generating}
          />
        )}

        <PhonePreview
          script={selectedScript}
          automation={health?.automation}
          backgrounds={backgrounds}
          voices={voicesData?.voices || []}
          onUpdateScript={handleSaveScript}
          onUploadBackground={async (file) => {
            await api.uploadBackground(file);
            await refreshAll();
            showToast(`Uploaded gameplay clip: ${file.name}`, "success");
          }}
          onRender={handleRender}
          onScheduleYoutube={handleScheduleYoutube}
          rendering={rendering}
          uploadingYt={uploadingYt}
        />
      </div>

      {/* Collapsible Live Pipeline Log Drawer */}
      <RenderDrawer logs={health?.automation?.recent_logs || []} />

      {/* Settings & YouTube OAuth Modal */}
      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        health={health}
        voicesData={voicesData}
        onSaveSettings={async (payload) => {
          await api.updateSettings(payload);
          await refreshAll();
          showToast("Updated Studio & Schedule configuration", "success");
        }}
        onUploadClientSecret={async (file) => {
          await api.uploadClientSecret(file);
          await refreshAll();
          showToast("Uploaded client_secret.json!", "success");
        }}
        onConnectYoutube={async () => {
          await api.connectYoutube();
          await refreshAll();
          showToast("Connected YouTube Channel!", "success");
        }}
        onDisconnectYoutube={async () => {
          await api.disconnectYoutube();
          await refreshAll();
          showToast("Disconnected YouTube OAuth token", "info");
        }}
        onUploadVoice={async (file, name, transcript, setAsDefault) => {
          await api.uploadVoice(file, name, transcript, setAsDefault);
          await refreshAll();
          showToast(`Uploaded & cloned voice "${name || file.name}"!`, "success");
        }}
        onSetDefaultVoice={async (voiceId) => {
          await api.setDefaultVoice(voiceId);
          await refreshAll();
          showToast("Updated default narrator voice!", "success");
        }}
        onDeleteVoice={async (filename) => {
          await api.deleteVoice(filename);
          await refreshAll();
          showToast("Deleted custom voice sample", "info");
        }}
        onDownloadBaseModel={async () => {
          const res = await api.downloadBaseVoiceModel();
          showToast(res.message || "Base model download started", "info");
          await refreshAll();
        }}
      />
    </div>
  );
}
