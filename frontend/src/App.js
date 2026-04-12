import { useState, useEffect, useCallback } from "react";
import "@/App.css";
import axios from "axios";

const getApi = () => `${process.env.REACT_APP_BACKEND_URL || window.location.origin}/api`;

function App() {
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
    try {
      const r = await axios.get(`${API}/videos`);
      setVideos(r.data);
    } catch (e) { console.error(e); }
  }, [API]);

  useEffect(() => { loadVideos(); }, [loadVideos]);

  // ─── Upload subject image ───────────────────────────────────────
  const handleSubjectUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    setUploading(true);
    setStatusMsg("Uploading image...");
    try {
      const uploaded = [];
      for (const file of files) {
        const fd = new FormData();
        fd.append("file", file);
        const mt = file.type.startsWith("video/") ? "video" : "image";
        const r = await axios.post(`${API}/upload-media?media_type=${mt}`, fd);
        uploaded.push(r.data);
      }
      setSubjectFiles(prev => [...prev, ...uploaded]);
      setStatusMsg("");
    } catch (e) {
      console.error(e);
      alert("Upload failed. Try again.");
    } finally { setUploading(false); }
  };

  // ─── Upload audio file ─────────────────────────────────────────
  const handleAudioUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setStatusMsg("Uploading audio...");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await axios.post(`${API}/upload-media?media_type=audio`, fd);
      setAudioFile(r.data);
      setStatusMsg("");
    } catch (e) {
      console.error(e);
      alert("Audio upload failed.");
    } finally { setUploading(false); }
  };

  // ─── YouTube extract ───────────────────────────────────────────
  const handleYouTube = async () => {
    if (!youtubeUrl.trim()) return;
    setExtracting(true);
    setStatusMsg("Extracting audio from YouTube (may take 30s)...");
    try {
      const r = await axios.post(`${API}/youtube-audio`, { youtube_url: youtubeUrl.trim() });
      setAudioFile(r.data);
      setYoutubeUrl("");
      setStatusMsg("");
      alert(`Song loaded: ${r.data.original_filename}`);
    } catch (e) {
      console.error(e);
      alert("YouTube extraction failed. Check the URL and try again.");
      setStatusMsg("");
    } finally { setExtracting(false); }
  };

  // ─── Build prompt & generate ───────────────────────────────────
  const buildPrompt = () => {
    let p = subject.trim() || "The subject";
    if (clothing.trim()) p += `. Wearing ${clothing.trim()}`;
    if (actions.trim()) p += `. ${actions.trim()}`;
    return p;
  };

  const handleGenerate = async () => {
    if (subjectFiles.length === 0) { alert("Upload at least one subject image"); return; }
    if (!subject.trim() && !actions.trim()) { alert("Describe who they are or what they should do"); return; }

    const prompt = buildPrompt();
    setGenerating(true);
    setCurrentVideo(null);

    try {
      const r = await axios.post(`${API}/generate-video`, {
        subject_media_ids: subjectFiles.map(f => f.id),
        audio_file_id: audioFile?.id || null,
        prompt,
        duration: 30
      });
      setCurrentVideo(r.data);
      pollStatus(r.data.id);
    } catch (e) {
      console.error(e);
      alert(e.response?.data?.detail || "Generation failed");
      setGenerating(false);
    }
  };

  const pollStatus = (id) => {
    const iv = setInterval(async () => {
      try {
        const r = await axios.get(`${API}/videos/${id}`);
        setCurrentVideo(r.data);
        if (r.data.status === "completed" || r.data.status === "failed") {
          clearInterval(iv);
          setGenerating(false);
          loadVideos();
        }
      } catch (e) { clearInterval(iv); setGenerating(false); }
    }, 5000);
  };

  const removeFile = (id) => setSubjectFiles(prev => prev.filter(f => f.id !== id));
  const canGenerate = !generating && !uploading && !extracting && subjectFiles.length > 0 && (subject.trim() || actions.trim());

  // ─── Render ────────────────────────────────────────────────────
  return (
    <div className="min-h-screen" style={{ backgroundColor: "#FFF4D2" }}>

      {/* Header */}
      <div className="p-6 md:p-12 text-center">
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight uppercase mb-3"
            style={{ fontFamily: "'Bricolage Grotesque', sans-serif", color: "#0A0A0A" }}
            data-testid="app-title">
          Dancing Dave's Swamp Donkeys & Spundunnits
        </h1>
        <p className="text-base md:text-lg max-w-2xl mx-auto" style={{ color: "#404040" }}>
          Upload anything. Add music. Describe the drip. Watch AI make it dance.
        </p>
      </div>

      <div className="px-4 md:px-12 pb-16 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          {/* ── LEFT: Inputs ────────────────────────────────── */}
          <div className="space-y-5">

            {/* 1) Subject image */}
            <div className="neo-card p-5 md:p-6" data-testid="subject-upload-section">
              <h3 className="text-xl md:text-2xl font-bold tracking-tight mb-3"
                  style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>
                1. DROP YOUR SUBJECT
              </h3>
              <label className="upload-zone block p-8 text-center shadow-[6px_6px_0px_0px_#0A0A0A] cursor-pointer">
                <input type="file" multiple accept="image/*,video/*" onChange={handleSubjectUpload}
                       className="hidden" disabled={uploading} data-testid="subject-file-input" />
                <div className="text-base font-bold uppercase">{uploading ? "UPLOADING..." : "TAP TO UPLOAD"}</div>
                <div className="text-xs mt-1" style={{ color: "#404040" }}>Dogs, humans, aliens, washing machines — whatever</div>
              </label>
              {subjectFiles.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2" data-testid="uploaded-subjects">
                  {subjectFiles.map(f => (
                    <div key={f.id} className="relative">
                      <img src={`${API}/files/${f.id}`} alt="" className="media-preview" />
                      <button onClick={() => removeFile(f.id)}
                              className="absolute -top-2 -right-2 bg-red-500 text-white w-5 h-5 flex items-center justify-center border-2 border-black text-xs font-bold"
                              data-testid={`remove-subject-${f.id}`}>x</button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 2) Music */}
            <div className="neo-card p-5 md:p-6" data-testid="audio-upload-section">
              <h3 className="text-xl md:text-2xl font-bold tracking-tight mb-3"
                  style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>
                2. PICK YOUR MUSIC
              </h3>

              {/* YouTube */}
              <div className="flex gap-2 mb-3">
                <input type="text" value={youtubeUrl} onChange={e => setYoutubeUrl(e.target.value)}
                       placeholder="Paste YouTube URL..."
                       className="flex-1 px-3 py-2 text-sm border-2 border-black focus:outline-none"
                       style={{ backgroundColor: "white" }}
                       disabled={extracting} data-testid="youtube-url-input" />
                <button onClick={handleYouTube} disabled={extracting || !youtubeUrl.trim()}
                        className="neo-button px-4 py-2 text-xs font-bold uppercase border-2 border-black"
                        style={{ backgroundColor: extracting ? "#E5E5E5" : "#87CEEB", boxShadow: "3px 3px 0 #0A0A0A" }}
                        data-testid="youtube-extract-btn">
                  {extracting ? "..." : "GET"}
                </button>
              </div>

              <div className="text-center text-xs font-bold mb-3">OR UPLOAD FILE</div>

              <label className="upload-zone block p-6 text-center shadow-[4px_4px_0px_0px_#0A0A0A] cursor-pointer">
                <input type="file" accept="audio/*" onChange={handleAudioUpload}
                       className="hidden" disabled={uploading} data-testid="audio-file-input" />
                <div className="text-sm font-bold uppercase">{audioFile ? `${audioFile.original_filename}` : "TAP TO UPLOAD AUDIO"}</div>
              </label>

              {audioFile && (
                <div className="mt-2 p-2 border-2 border-black text-xs font-bold" style={{ backgroundColor: "#98FB98" }}
                     data-testid="audio-loaded">
                  LOADED: {audioFile.original_filename}
                </div>
              )}
            </div>

            {/* 3) Prompt builder */}
            <div className="neo-card p-5 md:p-6" data-testid="prompt-section">
              <h3 className="text-xl md:text-2xl font-bold tracking-tight mb-3"
                  style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>
                3. DESCRIBE THE VIBE
              </h3>

              <label className="block text-xs font-bold uppercase mb-1">Who / What is this?</label>
              <input type="text" value={subject} onChange={e => setSubject(e.target.value)}
                     placeholder="Three pit bulls, a washing machine, two aliens..."
                     className="w-full px-3 py-2 text-sm border-2 border-black mb-3 focus:outline-none focus:shadow-[3px_3px_0_#FFB6C1]"
                     style={{ backgroundColor: "white" }} disabled={generating}
                     data-testid="subject-input" />

              <label className="block text-xs font-bold uppercase mb-1">Clothing / Jewelry / Grills</label>
              <input type="text" value={clothing} onChange={e => setClothing(e.target.value)}
                     placeholder="Baggy jeans, Alabama jerseys, iced out chains, platinum diamond grills..."
                     className="w-full px-3 py-2 text-sm border-2 border-black mb-3 focus:outline-none focus:shadow-[3px_3px_0_#FFB6C1]"
                     style={{ backgroundColor: "white" }} disabled={generating}
                     data-testid="clothing-input" />

              <label className="block text-xs font-bold uppercase mb-1">Dance Style / Actions</label>
              <textarea value={actions} onChange={e => setActions(e.target.value)}
                        placeholder="Dancing grunge style with a beer in one hand and a blunt in the other, head bobbing, slow grinding..."
                        className="w-full px-3 py-2 text-sm border-2 border-black focus:outline-none focus:shadow-[3px_3px_0_#FFB6C1]"
                        style={{ backgroundColor: "white", minHeight: "80px" }} disabled={generating}
                        data-testid="actions-input" />
            </div>

            {/* Generate button */}
            <button onClick={handleGenerate} disabled={!canGenerate}
                    className="neo-button w-full px-6 py-4 text-lg font-bold uppercase tracking-wide border-2 border-black"
                    style={{
                      backgroundColor: canGenerate ? "#FFB6C1" : "#E5E5E5",
                      color: "#0A0A0A",
                      boxShadow: "4px 4px 0 #0A0A0A",
                      cursor: canGenerate ? "pointer" : "not-allowed"
                    }}
                    data-testid="generate-button">
              {generating ? "GENERATING... (2-5 MIN)" : "GENERATE VIDEO"}
            </button>

            {statusMsg && <p className="text-center text-sm font-bold" data-testid="status-msg">{statusMsg}</p>}
          </div>

          {/* ── RIGHT: Preview ──────────────────────────────── */}
          <div>
            <div className="neo-card p-5 md:p-6" data-testid="video-preview-section">
              <h3 className="text-xl md:text-2xl font-bold tracking-tight mb-3"
                  style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>
                VIDEO PREVIEW
              </h3>

              {!currentVideo && (
                <div className="p-10 border-4 border-dashed border-black text-center" style={{ backgroundColor: "#E0F2FE" }}
                     data-testid="empty-preview">
                  <p className="text-base font-bold uppercase">YOUR VIDEO WILL APPEAR HERE</p>
                </div>
              )}

              {currentVideo && currentVideo.status === "generating" && (
                <div className="p-10 border-2 border-black text-center" style={{ backgroundColor: "#FFD700" }}
                     data-testid="generating-status">
                  <div className="overflow-hidden">
                    <div className="marquee text-lg font-bold uppercase">
                      GENERATING... CHOREOGRAPHING... STYLING...
                    </div>
                  </div>
                  <p className="mt-3 text-sm font-semibold">Takes 2-5 minutes. Don't close this page.</p>
                </div>
              )}

              {currentVideo && currentVideo.status === "pending" && (
                <div className="p-10 border-2 border-black text-center" style={{ backgroundColor: "#FFD700" }}
                     data-testid="pending-status">
                  <p className="text-lg font-bold uppercase">QUEUED...</p>
                  <p className="mt-2 text-sm">Starting soon.</p>
                </div>
              )}

              {currentVideo && currentVideo.status === "completed" && (
                <div data-testid="completed-video">
                  <video controls className="video-player" src={`${API}/video-file/${currentVideo.id}`}
                         data-testid="video-player" />
                  <div className="mt-3 p-3 border-2 border-black" style={{ backgroundColor: "#98FB98" }}>
                    <p className="font-bold text-sm">VIDEO COMPLETE!</p>
                    <p className="text-xs mt-1">{currentVideo.prompt}</p>
                  </div>
                </div>
              )}

              {currentVideo && currentVideo.status === "failed" && (
                <div className="p-8 border-2 border-black text-center" style={{ backgroundColor: "#FFB6C1" }}
                     data-testid="failed-status">
                  <p className="font-bold text-lg">GENERATION FAILED</p>
                  <p className="text-sm mt-2">{currentVideo.error_message || "Something went wrong"}</p>
                </div>
              )}
            </div>

            {/* History */}
            {videos.length > 0 && (
              <div className="mt-5 neo-card p-5" data-testid="previous-videos">
                <h4 className="text-lg font-bold mb-3" style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>
                  PREVIOUS GENERATIONS
                </h4>
                <div className="space-y-2">
                  {videos.slice(0, 8).map(v => (
                    <div key={v.id} className="p-2 border-2 border-black cursor-pointer hover:bg-gray-50"
                         onClick={() => setCurrentVideo(v)} data-testid={`video-history-${v.id}`}>
                      <div className="flex justify-between items-start">
                        <p className="text-xs font-semibold flex-1">{v.prompt.substring(0, 50)}...</p>
                        <span className="px-2 py-0.5 text-xs font-bold border border-black ml-2"
                              style={{ backgroundColor: v.status === "completed" ? "#98FB98" : v.status === "failed" ? "#FFB6C1" : "#FFD700" }}>
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

export default App;
