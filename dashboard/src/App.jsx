import React, { useEffect, useState } from 'react';

const API_BASE = 'http://127.0.0.1:8765';

const STYLES = [
  { id: 'tall_tale_3d', name: 'Tall Tale 3D', desc: '2D cartoon characters inside a 3D parallax stage (Weird History & Loopholes)' },
  { id: 'deep_dive_3d', name: 'Deep Dive 3D', desc: 'Zack D. style X-ray anatomy & neon scanner HUD (Body/Science Explainers)' },
  { id: 'inside_out', name: 'Inside Out', desc: 'Clean 2D split cutaway diagrams (Fast Science & Mechanics)' },
  { id: 'stick_story', name: 'Stick Story', desc: 'Expressive stick figures on blueprint grid (Survival Hacks & Hypotheticals)' },
  { id: 'night_file_3d', name: 'Night File 3D', desc: 'Noir spotlight & red conspiracy strings (Unsolved Mysteries)' },
  { id: 'paper_atlas', name: 'Paper Atlas', desc: 'Vintage parchment map & animated travel routes (Battles & Empires)' },
];

const LANGUAGES = [
  { code: 'hi', label: 'Hindi (hi-IN) — Default' },
  { code: 'es', label: 'Spanish (es-MX)' },
  { code: 'fr', label: 'French (fr-FR)' },
  { code: 'ja', label: 'Japanese (ja-JP)' },
  { code: 'pt', label: 'Portuguese (pt-BR)' },
  { code: 'de', label: 'German (de-DE)' },
  { code: 'en', label: 'English (en-US)' },
];

export default function App() {
  const [state, setState] = useState(null);
  const [backendOnline, setBackendOnline] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [activeTab, setActiveTab] = useState('inspector');
  const [showLogs, setShowLogs] = useState(true);

  // Live Story Editing State
  const [editMode, setEditMode] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editStyle, setEditStyle] = useState('tall_tale_3d');
  const [editLang, setEditLang] = useState('hi');
  const [editBeats, setEditBeats] = useState([]);

  // Custom Director Form (Default Hindi + English Subtitles)
  const [customStyle, setCustomStyle] = useState('tall_tale_3d');
  const [customLang, setCustomLang] = useState('hi');
  const [customTitle, setCustomTitle] = useState('');

  const fetchState = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/state`);
      if (!res.ok) throw new Error('Backend HTTP error');
      const data = await res.json();
      setState(data);
      setBackendOnline(true);
    } catch (err) {
      setBackendOnline(false);
    }
  };

  useEffect(() => {
    fetchState();
    const timer = setInterval(fetchState, 900);
    return () => clearInterval(timer);
  }, []);

  const videos = state?.videos || [];
  const currentVideo = videos.find((v) => v.id === selectedId) || videos[0] || null;
  const progress = state?.progress || {
    running: false,
    stage: 'Idle',
    percent: 0,
    detail: 'Waiting for command...',
    logs: [],
  };
  const isRendering = Boolean(progress.running);
  const schedule = state?.schedule || {
    generate_time: '18:00',
    upload_time: '21:00',
    timezone: 'Asia/Kolkata',
    default_language: 'hi',
    enabled: true,
  };

  const startEditingStory = (vid) => {
    if (!vid?.script) return;
    setEditTitle(vid.script.title || '');
    setEditStyle(vid.script.style || 'tall_tale_3d');
    setEditLang(vid.script.spoken_language || 'hi');
    setEditBeats(vid.script.beats.map((b) => ({ ...b })));
    setEditMode(true);
  };

  const handleSaveStoryEdits = async () => {
    if (!currentVideo) return;
    const res = await fetch(`${API_BASE}/api/story/update/${currentVideo.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: editTitle,
        style: editStyle,
        spoken_language: editLang,
        beats: editBeats,
      }),
    });
    const data = await res.json();
    setState(data);
    setEditMode(false);
  };

  const handleDraftStoryOnly = async (payload = {}) => {
    const res = await fetch(`${API_BASE}/api/story/draft`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        spoken_language: customLang || 'hi',
        style: customStyle,
        ...payload,
      }),
    });
    const data = await res.json();
    setState(data);
    if (data.videos?.[0]) setSelectedId(data.videos[0].id);
    setActiveTab('inspector');
  };

  const handleGenerateAndRender = async (payload = {}) => {
    const res = await fetch(`${API_BASE}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        spoken_language: 'hi',
        ...payload,
      }),
    });
    const data = await res.json();
    setState(data);
    if (data.videos?.[0]) setSelectedId(data.videos[0].id);
    setActiveTab('inspector');
  };

  const handleRenderStory = async (id) => {
    const res = await fetch(`${API_BASE}/api/render/${id}`, { method: 'POST' });
    const data = await res.json();
    setState(data);
  };

  const handleRejectStory = async (id, draftReplacement = true) => {
    const res = await fetch(`${API_BASE}/api/story/reject/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        draft_replacement: draftReplacement,
        spoken_language: schedule.default_language || 'hi',
      }),
    });
    const data = await res.json();
    setState(data);
    if (data.videos?.[0]) setSelectedId(data.videos[0].id);
    setEditMode(false);
  };

  const handleRejectReelOnly = async (id) => {
    const res = await fetch(`${API_BASE}/api/reel/reject/${id}`, { method: 'POST' });
    const data = await res.json();
    setState(data);
  };

  const handleStatusChange = async (id, newStatus) => {
    const res = await fetch(`${API_BASE}/api/review/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus }),
    });
    const data = await res.json();
    setState(data);
  };

  const handleCancelRender = async () => {
    const res = await fetch(`${API_BASE}/api/job/cancel`, { method: 'POST' });
    const data = await res.json();
    setState(data);
  };

  const handleClearLogs = async () => {
    const res = await fetch(`${API_BASE}/api/logs/clear`, { method: 'POST' });
    const data = await res.json();
    setState(data);
  };

  const handleToggleAutomation = async () => {
    const res = await fetch(`${API_BASE}/api/schedule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !schedule.enabled }),
    });
    const data = await res.json();
    setState(data);
  };

  return (
    <div className="studio-shell">
      {/* Top Header */}
      <header className="studio-header">
        <div className="brand-block">
          <div className="badge-row">
            <span className="brand-badge">ANTIGRAVITY INTERACTIVE STUDIO</span>
            <span className={`conn-pill ${backendOnline ? 'online' : 'offline'}`}>
              {backendOnline ? '● Backend Connected (Port 8765)' : '○ Backend Offline — Run start_studio.bat'}
            </span>
          </div>
          <h1>Faceless Animated Shorts & Reels Control Center</h1>
          <p>
            Default Voiceover: <strong>Hindi (hi-IN)</strong> • Subtitles: <strong>English Only</strong> • Duration:{' '}
            <strong>22s–28s (8 Beats)</strong>
          </p>
        </div>

        <div className="schedule-banner">
          <div className="schedule-step">
            <span className="step-time">{schedule.generate_time} IST</span>
            <span className="step-label">Daily 24s Hindi+EN Render</span>
          </div>
          <span className="step-arrow">➔</span>
          <div className="schedule-step">
            <span className="step-time">Auto QA Gate</span>
            <span className="step-label">20-28s + Audio + EN Subs</span>
          </div>
          <span className="step-arrow">➔</span>
          <div className="schedule-step">
            <span className="step-time">{schedule.upload_time} IST</span>
            <span className="step-label">YouTube Upload + IG Copy</span>
          </div>
          <button
            className={`pill-toggle ${schedule.enabled ? 'active' : 'paused'}`}
            onClick={handleToggleAutomation}
          >
            {schedule.enabled ? '● Daily 6PM Cron ON' : '○ Cron Paused'}
          </button>
        </div>

        <div className="header-actions">
          <button
            className="secondary-cta"
            disabled={!backendOnline || isRendering}
            onClick={() => handleDraftStoryOnly({ spoken_language: 'hi' })}
          >
            📝 Draft New Hindi Story First
          </button>
          <button
            className="primary-cta"
            disabled={!backendOnline || isRendering}
            onClick={() => handleGenerateAndRender({ spoken_language: 'hi' })}
          >
            {isRendering ? `⏳ Rendering (${progress.percent}%)...` : '⚡ Generate & Render 24s Reel Now'}
          </button>
        </div>
      </header>

      {/* Live Backend Activity & Real-Time Render Progress Panel */}
      <section className={`live-backend-bar ${isRendering ? 'active-render' : ''}`}>
        <div className="progress-top-row">
          <div className="stage-info">
            <span className={`pulse-dot ${isRendering ? 'running' : 'idle'}`} />
            <strong>Backend Engine:</strong>
            <span className="stage-badge">{progress.stage}</span>
            <span className="stage-detail">{progress.detail}</span>
          </div>
          <div className="progress-actions">
            <span className="pct-readout">{progress.percent}%</span>
            {isRendering && (
              <button className="btn-cancel-job" onClick={handleCancelRender}>
                ⏹️ Cancel Render
              </button>
            )}
            <button className="btn-log-toggle" onClick={() => setShowLogs(!showLogs)}>
              {showLogs ? '▼ Hide Backend Console' : '▲ Show Backend Console'}
            </button>
          </div>
        </div>

        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progress.percent}%` }} />
        </div>

        {showLogs && (
          <div className="console-drawer">
            <div className="console-header">
              <span>🖥️ LIVE BACKEND TERMINAL STREAM (scripts/server.py & pipeline.py)</span>
              <button onClick={handleClearLogs}>🧹 Clear Logs</button>
            </div>
            <div className="console-body">
              {(progress.logs || []).map((line, i) => (
                <div key={i} className="console-line">
                  {line}
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Main 2-Column Studio Grid */}
      <main className="studio-grid">
        {/* Left Column: 9:16 Vertical Video Preview & Interactive Reel Controls */}
        <section className="preview-column">
          <div className="panel-card">
            <div className="card-header">
              <h2>📱 9:16 Vertical Reel Player</h2>
              {currentVideo && (
                <span className={`status-badge ${currentVideo.status}`}>
                  {currentVideo.status === 'scheduled_9pm'
                    ? '✅ QA Passed • Scheduled 9:00 PM'
                    : currentVideo.status === 'rendering'
                    ? `⏳ Rendering (${progress.percent}%)`
                    : currentVideo.status === 'story_draft'
                    ? '📝 Story Draft (Not Rendered Yet)'
                    : currentVideo.status === 'reel_rejected'
                    ? '🚫 Reel Rejected (MP4 Deleted)'
                    : currentVideo.status}
                </span>
              )}
            </div>

            {currentVideo ? (
              <>
                <div className="phone-frame">
                  {currentVideo.video_url ? (
                    <video
                      key={currentVideo.video_url}
                      src={`${API_BASE}${currentVideo.video_url}`}
                      controls
                      autoPlay
                      loop
                      className="vertical-video"
                    />
                  ) : (
                    <div className="unrendered-placeholder">
                      <div className="placeholder-icon">{isRendering ? '⚙️' : '📝'}</div>
                      <h3>
                        {isRendering
                          ? `Rendering Frame-by-Frame (${progress.percent}%)`
                          : currentVideo.status === 'reel_rejected'
                          ? 'Reel Video Rejected & Deleted'
                          : 'Story Draft Ready for Review'}
                      </h3>
                      <p>
                        Review or edit the 8 Hindi + English-subtitle beats on the right, or click below to render the
                        24-second 9:16 video!
                      </p>
                      {!isRendering && (
                        <button className="primary-cta" onClick={() => handleRenderStory(currentVideo.id)}>
                          🎬 Render 24s Animated Reel Now
                        </button>
                      )}
                    </div>
                  )}
                </div>

                <div className="video-meta-strip">
                  <div>
                    <strong>🎙️ Voice:</strong> {currentVideo.spoken_language_label}
                  </div>
                  <div>
                    <strong>💬 Subs:</strong> <span className="highlight-yellow">English Only</span>
                  </div>
                  <div>
                    <strong>⏱️ Duration:</strong> {currentVideo.duration}s
                  </div>
                </div>

                {/* Interactive Reel & Story Action Buttons */}
                <div className="control-group-label">🎛️ REEL & STORY ACTIONS</div>
                <div className="review-actions">
                  <button
                    className="btn-approve"
                    disabled={!currentVideo.video_url || isRendering}
                    onClick={() => handleStatusChange(currentVideo.id, 'scheduled_9pm')}
                  >
                    ✅ Approve for 9PM Upload
                  </button>
                  <button
                    className="btn-rerender"
                    disabled={isRendering}
                    onClick={() => handleRenderStory(currentVideo.id)}
                  >
                    {currentVideo.video_url ? '🔄 Re-Render Reel' : '🎬 Render Reel'}
                  </button>
                </div>

                <div className="review-actions">
                  <button
                    className="btn-reject"
                    disabled={!currentVideo.video_url || isRendering}
                    onClick={() => handleRejectReelOnly(currentVideo.id)}
                    title="Deletes the rendered MP4 video but keeps the story script so you can edit or re-render it"
                  >
                    🚫 Reject Reel Only (Discard MP4)
                  </button>
                  <button
                    className="btn-reject-story"
                    disabled={isRendering}
                    onClick={() => handleRejectStory(currentVideo.id, true)}
                    title="Deletes this story completely and immediately drafts a brand-new Hindi story"
                  >
                    🗑️ Reject Story & Draft Next
                  </button>
                </div>

                {/* Automated QA Gate Scorecard */}
                {currentVideo.qa_report && (
                  <div className="qa-scorecard">
                    <h3>🛡️ Automated QA Review Gate (20s–58s Policy)</h3>
                    <div className="qa-grid">
                      {Object.entries(currentVideo.qa_report.checks || {}).map(([key, val]) => (
                        <div key={key} className={`qa-item ${val.passed ? 'pass' : 'fail'}`}>
                          <span className="qa-icon">{val.passed ? '✔' : '✖'}</span>
                          <div>
                            <div className="qa-name">{key.replace(/_/g, ' ').toUpperCase()}</div>
                            <div className="qa-detail">
                              {val.resolution ||
                                (val.duration_sec && `${val.duration_sec}s (${val.target_range})`) ||
                                (val.rms_db && `Loudness: ${val.rms_db} dB`) ||
                                (val.latin_character_ratio && `EN Ratio: ${val.latin_character_ratio * 100}%`) ||
                                (val.hook_score && `Hook Score: ${val.hook_score}/10`)}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="empty-state">
                <h3>Queue is Clean & Empty</h3>
                <p>
                  Click <strong>"📝 Draft New Hindi Story First"</strong> to inspect/edit a 24-second script before
                  rendering, or <strong>"⚡ Generate & Render 24s Reel Now"</strong>!
                </p>
                <div className="empty-cta-row">
                  <button
                    className="secondary-cta"
                    disabled={!backendOnline || isRendering}
                    onClick={() => handleDraftStoryOnly({ spoken_language: 'hi' })}
                  >
                    📝 Draft 24s Hindi Story
                  </button>
                  <button
                    className="primary-cta"
                    disabled={!backendOnline || isRendering}
                    onClick={() => handleGenerateAndRender({ spoken_language: 'hi' })}
                  >
                    ⚡ Generate & Render 24s Reel
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Right Column: Queue + Interactive Story Editor & Director */}
        <section className="inspector-column">
          {/* Queue Bar */}
          <div className="panel-card queue-card">
            <div className="card-header">
              <h2>🎞️ Stories & Rendered Reels Queue ({videos.length})</h2>
              <span className="sub-note">Default Audio: Hindi (hi-IN) • Subtitles: Strict English Only</span>
            </div>
            {videos.length > 0 ? (
              <div className="queue-strip">
                {videos.map((v) => (
                  <div
                    key={v.id}
                    className={`queue-pill ${currentVideo?.id === v.id ? 'selected' : ''}`}
                    onClick={() => {
                      setSelectedId(v.id);
                      setEditMode(false);
                    }}
                  >
                    <div className="q-top">
                      <span className="q-style">{v.style.replace(/_/g, ' ').toUpperCase()}</span>
                      <span className={`q-dot ${v.status}`}>{v.status.replace(/_/g, ' ')}</span>
                    </div>
                    <div className="q-title">{v.title}</div>
                    <div className="q-lang">
                      🔊 {v.spoken_language.toUpperCase()} → 💬 EN Subs ({v.duration}s)
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="queue-empty">No stories or reels in queue. Draft or generate one above!</div>
            )}
          </div>

          {/* Tabs: Story Inspector/Editor vs Custom Director */}
          <div className="panel-card">
            <div className="tab-bar">
              <button
                className={activeTab === 'inspector' ? 'active' : ''}
                onClick={() => setActiveTab('inspector')}
              >
                📝 Interactive Story Inspector & Beat Editor
              </button>
              <button
                className={activeTab === 'director' ? 'active' : ''}
                onClick={() => setActiveTab('director')}
              >
                🎬 Custom Story & Style Director
              </button>
            </div>

            {activeTab === 'inspector' && currentVideo?.script ? (
              <div className="script-inspector">
                <div className="script-summary">
                  <div>
                    <h3>{currentVideo.script.title}</h3>
                    <p>
                      {currentVideo.script.beats.length} Beats • Target Length: ~{currentVideo.duration}s (≥ 20–25s) •
                      Voice: <strong>{currentVideo.spoken_language_label}</strong> • Subtitles:{' '}
                      <strong>English Only</strong>
                    </p>
                  </div>
                  <div className="story-toolbar">
                    {!editMode ? (
                      <button className="btn-edit-story" onClick={() => startEditingStory(currentVideo)}>
                        ✏️ Edit Story & Beats
                      </button>
                    ) : (
                      <>
                        <button className="btn-save-story" onClick={handleSaveStoryEdits}>
                          💾 Save Story Changes
                        </button>
                        <button className="btn-cancel-edit" onClick={() => setEditMode(false)}>
                          Cancel
                        </button>
                      </>
                    )}
                    <button
                      className="btn-reject-story"
                      disabled={isRendering}
                      onClick={() => handleRejectStory(currentVideo.id, true)}
                    >
                      🚫 Reject Story & Draft Another
                    </button>
                  </div>
                </div>

                {editMode ? (
                  <div className="live-editor-box">
                    <div className="form-row">
                      <div>
                        <label className="form-label">Story Title</label>
                        <input
                          type="text"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                        />
                      </div>
                      <div>
                        <label className="form-label">Voiceover Language (Subtitles stay English Only)</label>
                        <select value={editLang} onChange={(e) => setEditLang(e.target.value)}>
                          {LANGUAGES.map((l) => (
                            <option key={l.code} value={l.code}>
                              {l.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div className="beats-list">
                      {editBeats.map((b, idx) => (
                        <div key={b.beat_id} className="beat-card editing">
                          <div className="beat-header">
                            <span className="beat-num">BEAT #{b.beat_id}</span>
                            <span className="beat-cue">🎥 {b.camera_action}</span>
                            <span className="beat-cue">😀 {b.character_expression}</span>
                            <span className="beat-cue">🔊 {b.sfx_cue}</span>
                          </div>
                          <div className="beat-dual-text">
                            <div className="spoken-box">
                              <label>🎙️ Spoken Audio Line ({editLang.toUpperCase()}):</label>
                              <textarea
                                rows={2}
                                value={b.spoken_text}
                                onChange={(e) => {
                                  const copy = [...editBeats];
                                  copy[idx] = { ...copy[idx], spoken_text: e.target.value };
                                  setEditBeats(copy);
                                }}
                              />
                            </div>
                            <div className="subtitle-box">
                              <label>💬 Burned-In English Subtitle (EN ONLY):</label>
                              <textarea
                                rows={2}
                                value={b.en_subtitle}
                                onChange={(e) => {
                                  const copy = [...editBeats];
                                  copy[idx] = { ...copy[idx], en_subtitle: e.target.value };
                                  setEditBeats(copy);
                                }}
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="beats-list">
                    {currentVideo.script.beats.map((b) => (
                      <div key={b.beat_id} className="beat-card">
                        <div className="beat-header">
                          <span className="beat-num">BEAT #{b.beat_id}</span>
                          <span className="beat-time">
                            {b.start_time !== undefined
                              ? `${b.start_time}s – ${b.end_time}s (${b.duration}s)`
                              : '~3.0s beat'}
                          </span>
                          <span className="beat-cue">🎥 {b.camera_action}</span>
                          <span className="beat-cue">😀 {b.character_expression}</span>
                          <span className="beat-cue">🔊 SFX: {b.sfx_cue}</span>
                          <span className="beat-cue">🪧 Prop: {b.prop}</span>
                        </div>

                        <div className="beat-dual-text">
                          <div className="spoken-box">
                            <label>🎙️ Spoken Audio ({currentVideo.spoken_language_label}):</label>
                            <p>{b.spoken_text}</p>
                          </div>
                          <div className="subtitle-box">
                            <label>💬 Burned-In Subtitle (STRICT ENGLISH ONLY):</label>
                            <p className="viral-caption">{b.en_subtitle}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="director-form">
                <h3>Direct a New 22–28s Animated Short</h3>
                <p>
                  Default voiceover is set to <strong>Hindi (hi-IN)</strong> and subtitles are strictly locked to{' '}
                  <strong>English Only</strong>. You can either <strong>Draft the Story First</strong> (to read/edit
                  before rendering) or <strong>Render Immediately</strong>.
                </p>

                <label className="form-label">1. Pick Visual Animation Style</label>
                <div className="style-grid">
                  {STYLES.map((s) => (
                    <div
                      key={s.id}
                      className={`style-option ${customStyle === s.id ? 'chosen' : ''}`}
                      onClick={() => setCustomStyle(s.id)}
                    >
                      <strong>{s.name}</strong>
                      <span>{s.desc}</span>
                    </div>
                  ))}
                </div>

                <div className="form-row">
                  <div>
                    <label className="form-label">2. Voiceover Language (Default: Hindi)</label>
                    <select value={customLang} onChange={(e) => setCustomLang(e.target.value)}>
                      {LANGUAGES.map((l) => (
                        <option key={l.code} value={l.code}>
                          {l.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="form-label">3. Burned-In Subtitle Language</label>
                    <input type="text" value="English Only (Locked)" disabled />
                  </div>
                </div>

                <label className="form-label">4. Optional Custom Story Title</label>
                <input
                  type="text"
                  placeholder="Leave blank to auto-pick next 8-beat viral Hindi story..."
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                />

                <div className="director-btn-row">
                  <button
                    className="secondary-cta"
                    disabled={!backendOnline || isRendering}
                    onClick={() =>
                      handleDraftStoryOnly({
                        style: customStyle,
                        spoken_language: customLang,
                        ...(customTitle.trim() ? { custom_title: customTitle.trim() } : {}),
                      })
                    }
                  >
                    📝 Draft Story Only (Review Before Render)
                  </button>
                  <button
                    className="primary-cta"
                    disabled={!backendOnline || isRendering}
                    onClick={() =>
                      handleGenerateAndRender({
                        style: customStyle,
                        spoken_language: customLang,
                        ...(customTitle.trim() ? { custom_title: customTitle.trim() } : {}),
                      })
                    }
                  >
                    🚀 Draft & Render 24s Reel Now
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
