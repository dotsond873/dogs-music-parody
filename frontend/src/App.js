import { useState, useEffect, useCallback } from "react";
import "@/App.css";
import axios from "axios";

const getApi = () => `${process.env.REACT_APP_BACKEND_URL || window.location.origin}/api`;
const LOGO_URL = "/file_00000000bda8720ca0c882cfd8b505ab.png";

// ═══════════════════════════════════════════════════════════════════
// WELCOME PAGE
// ═══════════════════════════════════════════════════════════════════
function WelcomePage({ onEnter }) {
  const API = getApi();
  const [hasVideo, setHasVideo] = useState(false);
  const [videoSrc, setVideoSrc] = useState("");
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
  axios
    .head(`${API}/welcome-video`)
    .then(() => {
      setHasVideo(true);
      setVideoSrc(`${API}/welcome-video?t=${Date.now()}`);
    })
    .catch(() => {
      setHasVideo(false);
    });
}, [API]);


  const handleUploadWelcome = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    // Check file size (max 50MB)
    if (file.size > 50 * 1024 * 1024) {
      alert("Video too large! Please use a video under 50MB.");
      return;
    }
    
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await axios.post(`${API}/welcome-video`, fd, { timeout: 120000 });
      setHasVideo(true);
      setVideoSrc(`${API}/welcome-video?t=${Date.now()}`);
      alert("Rocco's video uploaded!");
    } catch (err) {
      console.error(err);
      alert("Upload failed. Try a smaller video or check your connection.");
    } finally { setUploading(false); }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4" style={{ backgroundColor: "#0A0A0A" }}
         data-testid="welcome-page">

      {/* Logo */}
      {LOGO_URL && (
  <img src={LOGO_URL} alt="NAUGHTY DAWGZ" className="w-full max-w-2xl mb-6" data-testid="welcome-logo" />
)}

     
      {/* Video */}
<div className="w-full max-w-lg mb-8">
  <video
    src={videoSrc || `${API}/welcome-video?t=${Date.now()}`}
    autoPlay
    muted
    playsInline
    loop
    className="w-full border-2 border-yellow-500 shadow-lg"
    style={{ boxShadow: "0 0 30px rgba(255,215,0,0.3)" }}
    data-testid="welcome-video"
  />
</div>

      {/* Enter Button */}
      <button onClick={onEnter}
              className="neo-button px-12 py-4 text-xl font-black uppercase tracking-widest border-2 pulse-glow"
              style={{ backgroundColor: "#FFD700", color: "#0A0A0A", borderColor: "#FFD700" }}
              data-testid="enter-button">
        ENTER
      </button>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════
function MainApp() {
  const [subjectFiles, setSubjectFiles] = useState([]);
  const [audioFile, setAudioFile] = useState(null);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [subject, setSubject] = useState("");
  const [clothing, setClothing] = useState("");
  const [actions, setActions] = useState("");
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [videos, setVideos] = useState([]);
  const [currentVideo, setCurrentVideo] = useState(null);
  const [statusMsg, setStatusMsg] = useState("");

  const API = getApi();

  const loadVideos = useCallback(async () => {
    try { const r = await axios.get(`${API}/videos`); setVideos(r.data); } catch (e) { console.error(e); }
  }, [API]);

  useEffect(() => { loadVideos(); }, [loadVideos]);

  const handleSubjectUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    setUploading(true); setStatusMsg("Uploading...");
    try {
      const uploaded = [];
      for (const file of files) {
        const fd = new FormData(); fd.append("file", file);
        const mt = file.type.startsWith("video/") ? "video" : "image";
        const r = await axios.post(`${API}/upload-media?media_type=${mt}`, fd);
        uploaded.push(r.data);
      }
      setSubjectFiles(prev => [...prev, ...uploaded]); setStatusMsg("");
    } catch (e) { alert("Upload failed."); } finally { setUploading(false); }
  };

  const handleAudioUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true); setStatusMsg("Uploading audio...");
    try {
      const fd = new FormData(); fd.append("file", file);
      const r = await axios.post(`${API}/upload-media?media_type=audio`, fd, { timeout: 120000 });
      setAudioFile(r.data); setStatusMsg("");
    } catch (e) { alert("Audio upload failed."); setStatusMsg(""); } finally { setUploading(false); }
  };

  const handleYouTube = async () => {
    if (!youtubeUrl.trim()) return;
    setExtracting(true); setStatusMsg("Extracting from YouTube...");
    try {
      const r = await axios.post(`${API}/youtube-audio`, { youtube_url: youtubeUrl.trim() });
      setAudioFile(r.data); setYoutubeUrl(""); setStatusMsg("");
      alert(`Song loaded: ${r.data.original_filename}`);
    } catch (e) {
      alert("YouTube extraction failed. Check the URL."); setStatusMsg("");
    } finally { setExtracting(false); }
  };

  const buildPrompt = () => {
    let p = subject.trim() || "The subject";
    if (clothing.trim()) p += `. Wearing ${clothing.trim()}`;
    if (actions.trim()) p += `. ${actions.trim()}`;
    return p;
  };

  const handleGenerate = async () => {
    if (subjectFiles.length === 0) { alert("Upload at least one subject image"); return; }
    if (!subject.trim() && !actions.trim()) { alert("Describe who they are or what they should do"); return; }
    setGenerating(true); setCurrentVideo(null);
    try {
      const r = await axios.post(`${API}/generate-video`, {
        subject_media_ids: subjectFiles.map(f => f.id),
        audio_file_id: audioFile?.id || null,
        prompt: buildPrompt(), duration: 30
      });
      setCurrentVideo(r.data); pollStatus(r.data.id);
    } catch (e) { alert(e.response?.data?.detail || "Generation failed"); setGenerating(false); }
  };

  const pollStatus = (id) => {
    const iv = setInterval(async () => {
      try {
        const r = await axios.get(`${API}/videos/${id}`);
        setCurrentVideo(r.data);
        if (r.data.status === "completed" || r.data.status === "failed") { clearInterval(iv); setGenerating(false); loadVideos(); }
      } catch (e) { clearInterval(iv); setGenerating(false); }
    }, 5000);
  };

  const removeFile = (id) => setSubjectFiles(prev => prev.filter(f => f.id !== id));
  const canGenerate = !generating && !uploading && !extracting && subjectFiles.length > 0 && (subject.trim() || actions.trim());

  return (
    <div className="min-h-screen" style={{ backgroundColor: "#0A0A0A" }}>
      {/* Header */}
      <div className="p-4 md:p-8 text-center">
        <img src={LOGO_URL} alt="NAUGHTY DAWGZ" className="mx-auto w-full max-w-md mb-2" data-testid="app-logo" />
        <p className="text-sm md:text-base max-w-xl mx-auto" style={{ color: "#999" }}>
          Upload anything. Add music. Describe the drip. Watch AI make it dance.
        </p>
      </div>

      <div className="px-4 md:px-8 pb-16 max-w-6xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

          {/* LEFT COLUMN */}
          <div className="space-y-4">

            {/* Subject Upload */}
            <div className="neo-card p-4 md:p-5" data-testid="subject-upload-section">
              <h3 className="text-lg md:text-xl font-bold tracking-tight mb-2 gold-text">1. DROP YOUR SUBJECT</h3>
              <label className="upload-zone block p-6 text-center cursor-pointer">
                <input type="file" multiple accept="image/*,video/*" onChange={handleSubjectUpload}
                       className="hidden" disabled={uploading} data-testid="subject-file-input" />
                <div className="text-sm font-bold uppercase gold-text">{uploading ? "UPLOADING..." : "TAP TO UPLOAD"}</div>
                <div className="text-xs mt-1" style={{ color: "#888" }}>Dogs, humans, aliens, washing machines</div>
              </label>
              {subjectFiles.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2" data-testid="uploaded-subjects">
                  {subjectFiles.map(f => (
                    <div key={f.id} className="relative">
                      <img src={`${API}/files/${f.id}`} alt="" className="media-preview" />
                      <button onClick={() => removeFile(f.id)}
                              className="absolute -top-1 -right-1 bg-red-600 text-white w-5 h-5 flex items-center justify-center border border-red-800 text-xs font-bold rounded-full"
                              data-testid={`remove-subject-${f.id}`}>x</button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Music */}
            <div className="neo-card p-4 md:p-5" data-testid="audio-upload-section">
              <h3 className="text-lg md:text-xl font-bold tracking-tight mb-2 gold-text">2. PICK YOUR MUSIC</h3>

              {/* Primary: Upload audio file */}
              <label className="upload-zone block p-6 text-center cursor-pointer mb-3">
                <input type="file" accept="audio/*,video/*" onChange={handleAudioUpload} className="hidden" disabled={uploading}
                       data-testid="audio-file-input" />
                <div className="text-sm font-bold uppercase gold-text">{audioFile ? audioFile.original_filename : "TAP TO UPLOAD YOUR SONG"}</div>
                <div className="text-xs mt-1" style={{ color: "#888" }}>MP3, M4A, or any audio/video file from your phone</div>
              </label>

               {/* Secondary: Pixabay free music */}
<div className="text-center mt-4">
  <div
    className="text-center text-xs font-bold mb-2"
    style={{ color: "#666" }}
  >
    OR FIND FREE MUSIC
  </div>

  <a
    href="https://pixabay.com/music/"
    target="_blank"
    rel="noopener noreferrer"
    className="inline-block w-full px-4 py-3 text-sm font-black uppercase border-2 border-yellow-500"
    style={{
      backgroundColor: "#FFD700",
      color: "#0A0A0A",
      textDecoration: "none"
    }}
  >
    BROWSE PIXABAY MUSIC
  </a>

  <div
    className="text-center text-xs mt-2"
    style={{ color: "#666" }}
  >
    Download an MP3, then upload it above.
  </div>
</div> 

              {audioFile && (
                <div className="mt-2 p-2 border border-green-700 text-xs font-bold" style={{ backgroundColor: "rgba(0,128,0,0.15)", color: "#4ADE80" }}
                     data-testid="audio-loaded">
                  LOADED: {audioFile.original_filename}
                </div>
              )}
            </div>

            {/* Prompt Builder */}
            <div className="neo-card p-4 md:p-5" data-testid="prompt-section">
              <h3 className="text-lg md:text-xl font-bold tracking-tight mb-2 gold-text">3. DESCRIBE THE VIBE</h3>

              <label className="block text-xs font-bold uppercase mb-1 gold-text">Who / What?</label>
              <input type="text" value={subject} onChange={e => setSubject(e.target.value)}
                     placeholder="Three pit bulls, a washing machine, two aliens..."
                     className="w-full px-3 py-2 text-sm border-2 border-gray-600 focus:border-yellow-500 focus:outline-none mb-3 bg-black text-white"
                     disabled={generating} data-testid="subject-input" />

              <label className="block text-xs font-bold uppercase mb-1 gold-text">Clothing / Jewelry / Grills</label>
              <input type="text" value={clothing} onChange={e => setClothing(e.target.value)}
                     placeholder="Baggy jeans, Alabama jerseys, iced out chains, platinum grills..."
                     className="w-full px-3 py-2 text-sm border-2 border-gray-600 focus:border-yellow-500 focus:outline-none mb-3 bg-black text-white"
                     disabled={generating} data-testid="clothing-input" />

              <label className="block text-xs font-bold uppercase mb-1 gold-text">Dance Style / Actions</label>
              <textarea value={actions} onChange={e => setActions(e.target.value)}
                        placeholder="Grunge dancing with beer in one hand and blunt in the other..."
                        className="w-full px-3 py-2 text-sm border-2 border-gray-600 focus:border-yellow-500 focus:outline-none bg-black text-white"
                        style={{ minHeight: "70px" }} disabled={generating} data-testid="actions-input" />
            </div>

            {/* Generate */}
            <button onClick={handleGenerate} disabled={!canGenerate}
                    className="neo-button w-full px-6 py-4 text-lg font-black uppercase tracking-wide border-2"
                    style={{ backgroundColor: canGenerate ? "#FFD700" : "#333", color: "#0A0A0A",
                             borderColor: "#FFD700", boxShadow: "4px 4px 0 #333",
                             cursor: canGenerate ? "pointer" : "not-allowed" }}
                    data-testid="generate-button">
              {generating ? "GENERATING... (2-5 MIN)" : "GENERATE VIDEO"}
            </button>
            {statusMsg && <p className="text-center text-xs font-bold gold-text" data-testid="status-msg">{statusMsg}</p>}
          </div>

          {/* RIGHT COLUMN */}
          <div>
            <div className="neo-card p-4 md:p-5" data-testid="video-preview-section">
              <h3 className="text-lg md:text-xl font-bold tracking-tight mb-3 gold-text">VIDEO PREVIEW</h3>

              {!currentVideo && (
                <div className="p-8 border-2 border-dashed border-gray-600 text-center" data-testid="empty-preview">
                  <p className="text-sm font-bold uppercase" style={{ color: "#666" }}>YOUR VIDEO WILL APPEAR HERE</p>
                </div>
              )}

              {currentVideo && currentVideo.status === "generating" && (
                <div className="p-8 border-2 border-yellow-500 text-center" style={{ backgroundColor: "rgba(255,215,0,0.08)" }}
                     data-testid="generating-status">
                  <div className="overflow-hidden">
                    <div className="marquee text-base font-bold uppercase gold-text">
                      GENERATING... CHOREOGRAPHING... STYLING...
                    </div>
                  </div>
                  <p className="mt-3 text-xs" style={{ color: "#999" }}>2-5 minutes. Don't close the page.</p>
                </div>
              )}

              {currentVideo && currentVideo.status === "pending" && (
                <div className="p-8 border-2 border-yellow-500 text-center" data-testid="pending-status">
                  <p className="text-base font-bold uppercase gold-text">QUEUED...</p>
                </div>
              )}

              {currentVideo && currentVideo.status === "completed" && (
                <div data-testid="completed-video">
                  <video controls className="video-player" src={`${API}/video-file/${currentVideo.id}`} data-testid="video-player" />
                  <div className="mt-3 p-3 border border-green-700" style={{ backgroundColor: "rgba(0,128,0,0.15)" }}>
                    <p className="font-bold text-sm" style={{ color: "#4ADE80" }}>VIDEO COMPLETE!</p>
                    <p className="text-xs mt-1" style={{ color: "#999" }}>{currentVideo.prompt}</p>
                  </div>
                </div>
              )}

              {currentVideo && currentVideo.status === "failed" && (
                <div className="p-6 border-2 border-red-600 text-center" style={{ backgroundColor: "rgba(255,0,0,0.08)" }}
                     data-testid="failed-status">
                  <p className="font-bold text-base text-red-400">GENERATION FAILED</p>
                  <p className="text-xs mt-2" style={{ color: "#999" }}>{currentVideo.error_message || "Something went wrong"}</p>
                </div>
              )}
            </div>

            {/* History */}
            {videos.length > 0 && (
              <div className="mt-4 neo-card p-4" data-testid="previous-videos">
                <h4 className="text-base font-bold mb-3 gold-text">PREVIOUS GENERATIONS</h4>
                <div className="space-y-2">
                  {videos.slice(0, 8).map(v => (
                    <div key={v.id} className="p-2 border border-gray-700 cursor-pointer hover:border-yellow-500 transition-colors"
                         onClick={() => setCurrentVideo(v)} data-testid={`video-history-${v.id}`}>
                      <div className="flex justify-between items-start">
                        <p className="text-xs flex-1" style={{ color: "#CCC" }}>{v.prompt.substring(0, 50)}...</p>
                        <span className="px-2 py-0.5 text-xs font-bold ml-2"
                              style={{ backgroundColor: v.status === "completed" ? "rgba(0,128,0,0.3)" : v.status === "failed" ? "rgba(255,0,0,0.3)" : "rgba(255,215,0,0.3)",
                                       color: v.status === "completed" ? "#4ADE80" : v.status === "failed" ? "#F87171" : "#FFD700" }}>
                          {v.status.toUpperCase()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// APP (Router)
// ═══════════════════════════════════════════════════════════════════
function App() {
  const [entered, setEntered] = useState(false);

  if (!entered) {
    return <WelcomePage onEnter={() => setEntered(true)} />;
  }

  return <MainApp />;
}

export default App;
