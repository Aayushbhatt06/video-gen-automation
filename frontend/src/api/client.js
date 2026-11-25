const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    let errText = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      errText = data.detail || data.message || JSON.stringify(data);
    } catch {
      errText = await res.text();
    }
    throw new Error(errText);
  }
  return res.json();
}

export const api = {
  getHealth: () => request("/api/health"),

  // Scripts
  listScripts: () => request("/api/scripts"),
  getScript: (id) => request(`/api/scripts/${id}`),
  generateScript: (payload) =>
    request("/api/scripts/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateScript: (id, payload) =>
    request(`/api/scripts/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  rewriteBeat: (scriptId, beatId, payload) =>
    request(`/api/scripts/${scriptId}/beats/${beatId}/rewrite`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteScript: (id) =>
    request(`/api/scripts/${id}`, {
      method: "DELETE",
    }),
  getStoryHistory: () => request("/api/story-history"),

  // Backgrounds
  listBackgrounds: () => request("/api/backgrounds"),
  uploadBackground: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request("/api/backgrounds/upload", {
      method: "POST",
      body: fd,
    });
  },
  deleteBackground: (filename) =>
    request(`/api/backgrounds/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    }),

  // Voices & Voice Cloning
  listVoices: () => request("/api/voices"),
  uploadVoice: (file, displayName = "", transcript = "", setAsDefault = true) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("display_name", displayName);
    fd.append("transcript", transcript);
    fd.append("set_as_default", setAsDefault ? "true" : "false");
    return request("/api/voices/upload", {
      method: "POST",
      body: fd,
    });
  },
  setDefaultVoice: (voiceId) =>
    request("/api/voices/default", {
      method: "POST",
      body: JSON.stringify({ voice_id: voiceId }),
    }),
  deleteVoice: (filename) =>
    request(`/api/voices/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    }),
  downloadBaseVoiceModel: () =>
    request("/api/voices/download-base-model", {
      method: "POST",
    }),
  download17bVoiceModel: () =>
    request("/api/voices/download-17b-model", {
      method: "POST",
    }),

  // Rendering & Scheduled Upload
  renderScript: (scriptId, payload = {}) =>
    request(`/api/scripts/${scriptId}/render`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  scheduleYoutubeUpload: (scriptId) =>
    request(`/api/scripts/${scriptId}/schedule-youtube`, {
      method: "POST",
    }),

  // YouTube OAuth & Schedule Board
  getYoutubeStatus: () => request("/api/youtube/status"),
  uploadClientSecret: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request("/api/youtube/upload-client-secret", {
      method: "POST",
      body: fd,
    });
  },
  connectYoutube: () =>
    request("/api/youtube/connect", {
      method: "POST",
    }),
  disconnectYoutube: () =>
    request("/api/youtube/disconnect", {
      method: "POST",
    }),
  getSchedule: () => request("/api/schedule"),
  refreshSlotStatus: (slotId) =>
    request(`/api/schedule/${slotId}/refresh-status`, {
      method: "POST",
    }),
  publishSlotNow: (slotId) =>
    request(`/api/schedule/${slotId}/publish-now`, {
      method: "POST",
    }),
  deleteScheduleSlot: (slotId) =>
    request(`/api/schedule/${slotId}`, {
      method: "DELETE",
    }),

  // Autonomous Automation Loop & Settings
  getAutomationStatus: () => request("/api/automation/status"),
  startAutomation: () =>
    request("/api/automation/start", {
      method: "POST",
    }),
  stopAutomation: () =>
    request("/api/automation/stop", {
      method: "POST",
    }),
  runAutomationOnce: () =>
    request("/api/automation/run-once", {
      method: "POST",
    }),
  updateSettings: (payload) =>
    request("/api/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};
