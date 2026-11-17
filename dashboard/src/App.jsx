import React, { useEffect, useState } from 'react';

const API_BASE = 'http://127.0.0.1:8765';

const STYLES = [
  { id: 'auto', name: 'Auto-Match Reference Style', desc: 'Automatically picks the best animation style for your topic' },
  { id: 'tall_tale_3d', name: '2.5D Sitcom / Office Room', desc: 'Rohan, Meera & Biscuit / Weird laws & loopholes' },
  { id: 'stick_story', name: 'Doodle Cartoon World', desc: 'Bright outdoor houses, mountains & science gags' },
  { id: 'deep_dive_3d', name: 'Technical Blueprint HUD', desc: 'Dark engineering/body grid + live telemetry & stepper' },
  { id: 'night_file_3d', name: 'Mythic Silhouette', desc: 'Atmospheric golden/indigo skies, embers & royal silhouettes' },
  { id: 'inside_out', name: 'Flat-Vector Cutaway', desc: 'Side-profile road/vehicle comparisons & callout boxes' },
];

const LANGUAGES = [
  { code: 'hi', flag: '🇮🇳', name: 'Hinglish', label: 'Hinglish (hi-IN Casual)' },
  { code: 'en', flag: '🇺🇸', name: 'English', label: 'English (en-US Andrew)' },
  { code: 'es', flag: '🇪🇸', name: 'Spanish', label: 'Spanish (es-MX)' },
  { code: 'fr', flag: '🇫🇷', name: 'French', label: 'French (fr-FR)' },
  { code: 'ja', flag: '🇯🇵', name: 'Japanese', label: 'Japanese (ja-JP)' },
  { code: 'pt', flag: '🇧🇷', name: 'Portuguese', label: 'Portuguese (pt-BR)' },
  { code: 'de', flag: '🇩🇪', name: 'German', label: 'German (de-DE)' },
];

const REACTION_FX = ['none', 'sweat_drops', 'villain_red_eyes', 'storm_cloud', 'hearts', 'frost'];
const SFX_OPTIONS = ['vine_boom', 'pop', 'whoosh', 'ding', 'record_scratch'];

export default function App() {
  const [state, setState] = useState(null);
  const [backendOnline, setBackendOnline] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [viewMode, setViewMode] = useState('studio'); // 'studio' | 'create'
  const [filterTab, setFilterTab] = useState('all'); // 'all' | 'draft' | 'rendered' | 'scheduled'
  const [showConsole, setShowConsole] = useState(false);

  // New Script Generator Controls
  const [newTopic, setNewTopic] = useState('');
  const [newStyle, setNewStyle] = useState('auto');
  const [selectedLangs, setSelectedLangs] = useState(['hi', 'en']);
  const [ttsEngine, setTtsEngine] = useState('qwen3');

  // Selected Script Language Override & Clone
  const [renderLang, setRenderLang] = useState('hi');

  // Beat-by-Beat Script Editor
  const [editMode, setEditMode] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editStyle, setEditStyle] = useState('tall_tale_3d');
  const [editLang, setEditLang] = useState('hi');
  const [editBeats, setEditBeats] = useState([]);

  const fetchState = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/state`);
      if (!res.ok) throw new Error('HTTP error');
      const data = await res.json();
      setState(data);
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    }
  };

  useEffect(() => {
    fetchState();
    const timer = setInterval(fetchState, 900);
    return () => clearInterval(timer);
  }, []);

  const videos = state?.videos || [];
  const filteredVideos = videos.filter((v) => {
    if (filterTab === 'draft') return v.status === 'story_draft' || v.status === 'reel_rejected';
    if (filterTab === 'rendered') return Boolean(v.video_url);
    if (filterTab === 'scheduled') return v.status === 'scheduled_9pm';
    return true;
  });

  const currentVideo = videos.find((v) => v.id === selectedId) || filteredVideos[0] || videos[0] || null;
  const progress = state?.progress || { running: false, stage: 'Idle', percent: 0, detail: '', logs: [] };
  const isRendering = Boolean(progress.running);
  const schedule = state?.schedule || { generate_time: '18:00', upload_time: '21:00', enabled: true };

  useEffect(() => {
    if (currentVideo) {
      setRenderLang(currentVideo.spoken_language || 'hi');
    }
  }, [currentVideo?.id]);

  const toggleLanguageChoice = (code) => {
    setSelectedLangs((prev) => {
      if (prev.includes(code)) {
        return prev.length === 1 ? prev : prev.filter((c) => c !== code);
      }
      return [...prev, code];
    });
  };

  const handleCreateScripts = async (renderNow) => {
    const res = await fetch(`${API_BASE}/api/script/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: newTopic.trim(),
        style: newStyle,
        languages: selectedLangs,
        tts_engine: ttsEngine,
        render_immediately: renderNow,
      }),
    });
    const data = await res.json();
    setState(data);
    if (data.videos?.[0]) {
      setSelectedId(data.videos[0].id);
    }
    setNewTopic('');
    setViewMode('studio');
    setEditMode(false);
  };

  const handleDeleteScript = async (id, e) => {
    if (e) e.stopPropagation();
    const res = await fetch(`${API_BASE}/api/script/delete/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ draft_replacement: false }),
    });
    const data = await res.json();
    setState(data);
    if (selectedId === id) {
      setSelectedId(data.videos?.[0]?.id || null);
      setEditMode(false);
    }
  };

  const handleClearAll = async () => {
    const res = await fetch(`${API_BASE}/api/queue/clear`, { method: 'POST' });
    const data = await res.json();
    setState(data);
    setSelectedId(null);
    setEditMode(false);
  };

  const handleRenderVideo = async (id, langOverride) => {
    const res = await fetch(`${API_BASE}/api/render/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...(langOverride ? { spoken_language: langOverride } : {}),
        tts_engine: ttsEngine,
      }),
    });
    const data = await res.json();
    setState(data);
  };

  const handleCloneIntoLanguage = async (id, targetLang, renderNow = false) => {
    const res = await fetch(`${API_BASE}/api/script/clone/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ spoken_language: targetLang, render_immediately: renderNow }),
    });
    const data = await res.json();
    setState(data);
    if (data.videos?.[0]) setSelectedId(data.videos[0].id);
  };

  const handleDeleteReelOnly = async (id) => {
    const res = await fetch(`${API_BASE}/api/reel/delete/${id}`, { method: 'POST' });
    const data = await res.json();
    setState(data);
  };

  const handleApproveReel = async (id) => {
    const res = await fetch(`${API_BASE}/api/review/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'scheduled_9pm' }),
    });
    const data = await res.json();
    setState(data);
  };

  const startEditing = (vid) => {
    if (!vid?.script) return;
    setEditTitle(vid.script.title || '');
    setEditStyle(vid.script.style || 'tall_tale_3d');
    setEditLang(vid.script.spoken_language || 'hi');
    setEditBeats((vid.script.beats || []).map((b) => ({ ...b })));
    setEditMode(true);
  };

  const handleSaveEdits = async () => {
    if (!currentVideo) return;
    const res = await fetch(`${API_BASE}/api/script/update/${currentVideo.id}`, {
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

  const handleAddBeat = () => {
    const nextNum = editBeats.length + 1;
    setEditBeats([
      ...editBeats,
      {
        beat_id: nextNum,
        speaker: nextNum % 2 === 0 ? 'meera' : 'rohan',
        speaker_gender: nextNum % 2 === 0 ? 'female' : 'male',
        spoken_text: 'Rohan: भाई ये नया सीन तो और भी crazy है!',
        en_subtitle: 'Bro, wait till you see this next crazy part!',
        reaction_fx: 'none',
        sfx_cue: 'pop',
        character_expression: 'shocked',
      },
    ]);
  };

  const handleRemoveBeat = (idx) => {
    if (editBeats.length <= 4) return;
    const updated = editBeats.filter((_, i) => i !== idx).map((b, i) => ({ ...b, beat_id: i + 1 }));
    setEditBeats(updated);
  };

  const handleCancelJob = async () => {
    const res = await fetch(`${API_BASE}/api/job/cancel`, { method: 'POST' });
    setState(await res.json());
  };

  const handleScheduleToggle = async () => {
    const res = await fetch(`${API_BASE}/api/schedule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !schedule.enabled }),
    });
    setState(await res.json());
  };

  const langObj = (code) => LANGUAGES.find((l) => l.code === code) || LANGUAGES[0];

  return (
    <div className="app-shell">
      {/* Top Studio Bar */}
      <header className="topbar">
        <div className="topbar-left">
          <div className="logo-badge">2D SHORTS STUDIO</div>
          <div>
            <h1>Autonomous Shorts & Reels Control Center</h1>
            <div className="conn-row">
              <span className={`conn-dot ${backendOnline ? 'on' : 'off'}`} />
              <span>{backendOnline ? 'Backend Connected (:8765)' : 'Backend Offline — Run start_studio.bat'}</span>
              <span className="sep">•</span>
              <span>Subtitles: Strictly English Only (.ASS)</span>
            </div>
          </div>
        </div>

        <div className="topbar-center">
          <span className="cron-info">
            Daily Auto: <strong>{schedule.generate_time}</strong> Draft & Render ➔ <strong>{schedule.upload_time}</strong> YT
          </span>
          <button className={`cron-btn ${schedule.enabled ? 'active' : 'off'}`} onClick={handleScheduleToggle}>
            {schedule.enabled ? '● Cron ON' : '○ Cron OFF'}
          </button>
        </div>

        <div className="topbar-actions">
          <button
            className={`btn-nav ${viewMode === 'create' ? 'active' : ''}`}
            disabled={!backendOnline}
            onClick={() => setViewMode(viewMode === 'create' ? 'studio' : 'create')}
          >
            {viewMode === 'create' ? '← Back to Studio' : '✨ + Generate New Script'}
          </button>
          <button className="btn-ghost" onClick={() => setShowConsole(!showConsole)}>
            🖥️ {showConsole ? 'Hide Logs' : 'Console Logs'}
          </button>
        </div>
      </header>

      {/* Live Progress Bar (Always visible when rendering or logs toggled) */}
      {(isRendering || showConsole) && (
        <section className={`progress-panel ${isRendering ? 'rendering' : ''}`}>
          <div className="prog-row">
            <div className="prog-status">
              <span className={`pulse ${isRendering ? 'live' : ''}`} />
              <strong>{progress.stage}</strong>
              <span className="prog-detail">{progress.detail}</span>
            </div>
            <div className="prog-right">
              <span className="prog-pct">{progress.percent}%</span>
              {isRendering && (
                <button className="btn-danger-sm" onClick={handleCancelJob}>
                  ⏹️ Cancel Render
                </button>
              )}
              <button
                className="btn-ghost-sm"
                onClick={async () => setState(await (await fetch(`${API_BASE}/api/logs/clear`, { method: 'POST' })).json())}
              >
                Clear Logs
              </button>
            </div>
          </div>
          {isRendering && (
            <div className="prog-track">
              <div className="prog-fill" style={{ width: `${progress.percent}%` }} />
            </div>
          )}
          {showConsole && (
            <div className="console-box">
              {(progress.logs || []).map((ln, i) => (
                <div key={i}>{ln}</div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Main Split Layout: Library Sidebar + Active Workspace */}
      <div className="workspace">
        {/* Left Sidebar: Scripts & Reels Library */}
        <aside className="sidebar">
          <div className="sidebar-head">
            <h2>Scripts & Reels ({videos.length})</h2>
            {videos.length > 0 && (
              <button className="btn-danger-xs" disabled={isRendering} onClick={handleClearAll}>
                Clear All
              </button>
            )}
          </div>

          <div className="filter-tabs">
            {[
              ['all', 'All'],
              ['draft', 'Drafts'],
              ['rendered', 'Videos'],
              ['scheduled', '9PM'],
            ].map(([k, lbl]) => (
              <button
                key={k}
                className={filterTab === k ? 'active' : ''}
                onClick={() => setFilterTab(k)}
              >
                {lbl}
              </button>
            ))}
          </div>

          <div className="library-list">
            {filteredVideos.length === 0 ? (
              <div className="empty-lib">
                <p>No scripts here yet.</p>
                <button className="btn-primary-sm" onClick={() => setViewMode('create')}>
                  ✨ + Generate New Script
                </button>
              </div>
            ) : (
              filteredVideos.map((v) => {
                const l = langObj(v.spoken_language);
                return (
                  <div
                    key={v.id}
                    className={`lib-card ${currentVideo?.id === v.id && viewMode === 'studio' ? 'selected' : ''}`}
                    onClick={() => {
                      setSelectedId(v.id);
                      setViewMode('studio');
                      setEditMode(false);
                    }}
                  >
                    <div className="lib-card-top">
                      <span className="lang-chip">
                        {l.flag} {l.name}
                      </span>
                      <span className={`state-chip ${v.status}`}>
                        {v.status === 'scheduled_9pm'
                          ? '✅ 9PM'
                          : v.status === 'rendering'
                          ? '⏳ Rendering'
                          : '📝 Draft'}
                      </span>
                      <button
                        className="lib-del-btn"
                        title="Delete this script & video"
                        disabled={isRendering && v.status === 'rendering'}
                        onClick={(e) => handleDeleteScript(v.id, e)}
                      >
                        🗑️
                      </button>
                    </div>
                    <div className="lib-title">{v.title}</div>
                    <div className="lib-meta">
                      <span>{v.style.replace(/_/g, ' ')}</span>
                      <span>•</span>
                      <span>{v.duration}s</span>
                      <span>•</span>
                      <span>{v.video_url ? '🎬 MP4 Ready' : 'No Video'}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </aside>

        {/* Right Main Area */}
        <main className="main-area">
          {viewMode === 'create' ? (
            /* ================= NEW SCRIPT GENERATOR PANEL ================= */
            <section className="card create-panel">
              <div className="panel-title-row">
                <div>
                  <h2>✨ Generate New 2D Animated Script</h2>
                  <p>
                    Choose your topic, pick one or multiple voiceover languages, and select the 2D animation style.
                    Subtitles are always burned in <strong>English Only</strong>.
                  </p>
                </div>
              </div>

              <div className="form-section">
                <label>1. Story Topic (Leave blank for a random unseen comedy skit)</label>
                <div className="topic-row">
                  <input
                    type="text"
                    placeholder="e.g. Why Indians keep plastic bags inside a bigger plastic bag..."
                    value={newTopic}
                    onChange={(e) => setNewTopic(e.target.value)}
                  />
                  {newTopic && (
                    <button className="btn-ghost" onClick={() => setNewTopic('')}>
                      Clear
                    </button>
                  )}
                </div>
              </div>

              <div className="form-section">
                <div className="lang-header-row">
                  <label>2. Voiceover Language(s) to Generate</label>
                  <div className="preset-pills">
                    <button onClick={() => setSelectedLangs(['hi'])}>Only Hinglish</button>
                    <button onClick={() => setSelectedLangs(['en'])}>Only English</button>
                    <button onClick={() => setSelectedLangs(['hi', 'en'])}>Both (Hinglish + English)</button>
                  </div>
                </div>
                <div className="lang-grid">
                  {LANGUAGES.map((l) => {
                    const active = selectedLangs.includes(l.code);
                    return (
                      <button
                        key={l.code}
                        type="button"
                        className={`lang-option ${active ? 'active' : ''}`}
                        onClick={() => toggleLanguageChoice(l.code)}
                      >
                        <span className="l-flag">{l.flag}</span>
                        <div>
                          <div className="l-name">{l.name}</div>
                          <div className="l-sub">{l.label}</div>
                        </div>
                        <span className="l-check">{active ? '✔' : '+'}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="form-section">
                <label>3. Voice Engine (Alibaba Qwen3-TTS Local GPU)</label>
                <div className="style-grid">
                  <div
                    className={`style-card ${ttsEngine === 'qwen3' ? 'active' : ''}`}
                    onClick={() => setTtsEngine('qwen3')}
                  >
                    <strong>🧠 Qwen3-TTS 0.6B (Local GPU — Default)</strong>
                    <span>Natural voice for English/Global languages + automatic Hinglish bilingual support</span>
                  </div>
                  <div
                    className={`style-card ${ttsEngine === 'edge' ? 'active' : ''}`}
                    onClick={() => setTtsEngine('edge')}
                  >
                    <strong>☁️ Edge-TTS Neural</strong>
                    <span>Lightweight Microsoft Edge neural voices (zero GPU memory)</span>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <label>4. 2D Cartoon Animation Style</label>
                <div className="style-grid">
                  {STYLES.map((s) => (
                    <div
                      key={s.id}
                      className={`style-card ${newStyle === s.id ? 'active' : ''}`}
                      onClick={() => setNewStyle(s.id)}
                    >
                      <strong>{s.name}</strong>
                      <span>{s.desc}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="create-footer">
                <button
                  className="btn-secondary"
                  disabled={!backendOnline || isRendering}
                  onClick={() => handleCreateScripts(false)}
                >
                  📝 Generate {selectedLangs.length > 1 ? `${selectedLangs.length} Script Drafts` : 'Script Draft'} Only
                </button>
                <button
                  className="btn-primary"
                  disabled={!backendOnline || isRendering}
                  onClick={() => handleCreateScripts(true)}
                >
                  🎬 Generate & Render {selectedLangs.length > 1 ? 'Both Videos' : 'Video'} Now
                </button>
              </div>
            </section>
          ) : !currentVideo ? (
            /* ================= EMPTY STUDIO STATE ================= */
            <section className="card empty-studio">
              <h2>Welcome to Your 2D Animated Shorts Studio</h2>
              <p>Create a new Hinglish, English, or dual-language script to get started.</p>
              <button className="btn-primary" disabled={!backendOnline} onClick={() => setViewMode('create')}>
                ✨ + Generate New Script
              </button>
            </section>
          ) : (
            /* ================= ACTIVE SCRIPT & VIDEO STUDIO ================= */
            <div className="studio-split">
              {/* Video Player & Render Controls */}
              <section className="card player-col">
                <div className="phone-box">
                  {currentVideo.video_url ? (
                    <video
                      key={currentVideo.video_url}
                      src={`${API_BASE}${currentVideo.video_url}`}
                      controls
                      autoPlay
                      loop
                    />
                  ) : (
                    <div className="phone-placeholder">
                      <div className="ph-emoji">{currentVideo.status === 'rendering' ? '⚙️' : '🎬'}</div>
                      <h3>{currentVideo.status === 'rendering' ? `Rendering ${progress.percent}%` : 'Draft Ready'}</h3>
                      <p>Review or edit the script on the right, pick the language below, and render your 9:16 MP4.</p>
                    </div>
                  )}
                </div>

                {/* Per-Video Language & Render Control */}
                <div className="control-box">
                  <label>🎙️ Voice Engine & Language (Subtitles: English Only)</label>
                  <select
                    value={ttsEngine}
                    onChange={(e) => setTtsEngine(e.target.value)}
                    style={{ marginBottom: '8px' }}
                  >
                    <option value="qwen3">🧠 Qwen3-TTS 0.6B (Local GPU) + Hinglish Auto</option>
                    <option value="edge">☁️ Edge-TTS Neural Voices</option>
                  </select>
                  <div className="render-lang-row">
                    <select value={renderLang} onChange={(e) => setRenderLang(e.target.value)}>
                      {LANGUAGES.map((l) => (
                        <option key={l.code} value={l.code}>
                          {l.flag} {l.label}
                        </option>
                      ))}
                    </select>
                    <button
                      className="btn-primary"
                      disabled={isRendering || !backendOnline}
                      onClick={() => handleRenderVideo(currentVideo.id, renderLang)}
                    >
                      {currentVideo.video_url ? '🔄 Re-Render' : '🎬 Render Video'}
                    </button>
                  </div>

                  {/* Quick Clone into Opposite Language */}
                  <div className="clone-row">
                    <span>Need another language version?</span>
                    {currentVideo.spoken_language !== 'en' && (
                      <button
                        className="btn-ghost-sm"
                        disabled={isRendering}
                        onClick={() => handleCloneIntoLanguage(currentVideo.id, 'en', false)}
                      >
                        🇺🇸 Clone as English
                      </button>
                    )}
                    {currentVideo.spoken_language !== 'hi' && (
                      <button
                        className="btn-ghost-sm"
                        disabled={isRendering}
                        onClick={() => handleCloneIntoLanguage(currentVideo.id, 'hi', false)}
                      >
                        🇮🇳 Clone as Hinglish
                      </button>
                    )}
                  </div>
                </div>

                {/* Approve / Delete Video / Delete Script */}
                <div className="action-stack">
                  <button
                    className="btn-approve"
                    disabled={!currentVideo.video_url || isRendering}
                    onClick={() => handleApproveReel(currentVideo.id)}
                  >
                    ✅ Approve & Schedule 9:00 PM YouTube
                  </button>
                  <div className="two-btns">
                    <button
                      className="btn-warn"
                      disabled={!currentVideo.video_url || isRendering}
                      onClick={() => handleDeleteReelOnly(currentVideo.id)}
                    >
                      🗑️ Delete Video Only
                    </button>
                    <button
                      className="btn-danger"
                      disabled={isRendering}
                      onClick={() => handleDeleteScript(currentVideo.id)}
                    >
                      ❌ Delete Script
                    </button>
                  </div>
                </div>

                {/* QA Gate Summary */}
                {currentVideo.qa_report && (
                  <div className="qa-box">
                    <h4>🛡️ Automated QA Report</h4>
                    <div className="qa-pills">
                      {Object.entries(currentVideo.qa_report.checks || {}).map(([k, val]) => (
                        <div key={k} className={`qa-pill ${val.passed ? 'ok' : 'bad'}`}>
                          <span>{val.passed ? '✔' : '✖'}</span>
                          <span>{k.replace(/_/g, ' ')}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>

              {/* Script, Cast & Shot-by-Shot Editor */}
              <section className="card script-col">
                <div className="script-top">
                  <div>
                    <div className="script-badges">
                      <span className="lang-chip">
                        {langObj(currentVideo.spoken_language).flag} {currentVideo.spoken_language_label}
                      </span>
                      <span className="sub-chip">💬 English-Only Subtitles</span>
                      <span className="sub-chip">⏱️ {currentVideo.duration}s</span>
                    </div>
                    <h2>{currentVideo.script?.title}</h2>
                  </div>

                  <div className="script-btns">
                    {!editMode ? (
                      <button className="btn-secondary" onClick={() => startEditing(currentVideo)}>
                        ✏️ Edit Script & Shots
                      </button>
                    ) : (
                      <>
                        <button className="btn-approve" onClick={handleSaveEdits}>
                          💾 Save Script
                        </button>
                        <button className="btn-ghost" onClick={() => setEditMode(false)}>
                          Cancel
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Cast & Set Design Sheet */}
                {currentVideo.script?.production_bible && (
                  <div className="cast-sheet">
                    <div className="cast-title">
                      🎭 Cast & Set: <strong>{currentVideo.script.production_bible.era_and_setting}</strong>
                    </div>
                    <div className="cast-chips">
                      {(currentVideo.script.production_bible.cast || []).map((c) => (
                        <span key={c.id} className="cast-chip">
                          {c.gender === 'female' ? '👩' : '👨'} {c.name} · {c.costume.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {editMode ? (
                  <div className="editor-area">
                    <div className="editor-meta-grid">
                      <div>
                        <label>Title</label>
                        <input type="text" value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
                      </div>
                      <div>
                        <label>Animation Style</label>
                        <select value={editStyle} onChange={(e) => setEditStyle(e.target.value)}>
                          {STYLES.filter((s) => s.id !== 'auto').map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label>Voiceover Language</label>
                        <select value={editLang} onChange={(e) => setEditLang(e.target.value)}>
                          {LANGUAGES.map((l) => (
                            <option key={l.code} value={l.code}>
                              {l.flag} {l.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div className="shots-list">
                      {editBeats.map((b, idx) => (
                        <div key={b.beat_id} className="shot-card editing">
                          <div className="shot-head">
                            <span className="shot-num">SHOT #{b.beat_id}</span>
                            <select
                              value={b.speaker_gender || 'male'}
                              onChange={(e) => {
                                const cp = [...editBeats];
                                cp[idx] = { ...cp[idx], speaker_gender: e.target.value };
                                setEditBeats(cp);
                              }}
                            >
                              <option value="male">👨 Male Voice</option>
                              <option value="female">👩 Female Voice</option>
                            </select>
                            <select
                              value={b.reaction_fx || 'none'}
                              onChange={(e) => {
                                const cp = [...editBeats];
                                cp[idx] = { ...cp[idx], reaction_fx: e.target.value };
                                setEditBeats(cp);
                              }}
                            >
                              {REACTION_FX.map((fx) => (
                                <option key={fx} value={fx}>
                                  FX: {fx}
                                </option>
                              ))}
                            </select>
                            <select
                              value={b.sfx_cue || 'pop'}
                              onChange={(e) => {
                                const cp = [...editBeats];
                                cp[idx] = { ...cp[idx], sfx_cue: e.target.value };
                                setEditBeats(cp);
                              }}
                            >
                              {SFX_OPTIONS.map((sx) => (
                                <option key={sx} value={sx}>
                                  SFX: {sx}
                                </option>
                              ))}
                            </select>
                            <button
                              className="btn-danger-xs"
                              disabled={editBeats.length <= 4}
                              onClick={() => handleRemoveBeat(idx)}
                            >
                              Remove
                            </button>
                          </div>
                          <div className="shot-texts">
                            <div>
                              <label>Spoken Line ({editLang.toUpperCase()})</label>
                              <textarea
                                rows={2}
                                value={b.spoken_text}
                                onChange={(e) => {
                                  const cp = [...editBeats];
                                  cp[idx] = { ...cp[idx], spoken_text: e.target.value };
                                  setEditBeats(cp);
                                }}
                              />
                            </div>
                            <div>
                              <label>English Subtitle (EN Only)</label>
                              <textarea
                                rows={2}
                                value={b.en_subtitle}
                                onChange={(e) => {
                                  const cp = [...editBeats];
                                  cp[idx] = { ...cp[idx], en_subtitle: e.target.value };
                                  setEditBeats(cp);
                                }}
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <button className="btn-secondary full-w" onClick={handleAddBeat}>
                      + Add New Shot
                    </button>
                  </div>
                ) : (
                  <div className="shots-list">
                    {(currentVideo.script?.beats || []).map((b) => (
                      <div key={b.beat_id} className="shot-card">
                        <div className="shot-head">
                          <span className="shot-num">SHOT #{b.beat_id}</span>
                          {b.start_time !== undefined && (
                            <span className="shot-time">
                              {b.start_time}s – {b.end_time}s
                            </span>
                          )}
                          <span className="shot-tag">
                            {b.speaker_gender === 'female' ? '👩' : '👨'} {b.speaker_name || b.speaker || 'Narrator'}
                          </span>
                          {b.reaction_fx && b.reaction_fx !== 'none' && (
                            <span className="shot-tag fx">⚡ {b.reaction_fx}</span>
                          )}
                          <span className="shot-tag">🔊 {b.sfx_cue}</span>
                          <span className="shot-tag props">
                            🎨 {(b.props || []).map((p) => p.kind).join(', ') || b.prop}
                          </span>
                        </div>
                        <div className="shot-texts">
                          <div className="t-box">
                            <label>🎙️ Spoken Audio</label>
                            <p>{b.spoken_text}</p>
                          </div>
                          <div className="t-box en">
                            <label>💬 English Subtitle</label>
                            <p>{b.en_subtitle}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
