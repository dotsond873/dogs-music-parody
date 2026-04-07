import { useState, useEffect } from "react";
import "@/App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [subjectFiles, setSubjectFiles] = useState([]);
  const [audioFile, setAudioFile] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [duration] = useState(30);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [videos, setVideos] = useState([]);
  const [currentVideo, setCurrentVideo] = useState(null);
  const [uploadProgress, setUploadProgress] = useState("");

  useEffect(() => {
    loadVideos();
  }, []);

  const loadVideos = async () => {
    try {
      const response = await axios.get(`${API}/videos`);
      setVideos(response.data);
    } catch (error) {
      console.error("Failed to load videos:", error);
    }
  };

  const handleSubjectUpload = async (e) => {
    const files = Array.from(e.target.files);
    setUploading(true);
    setUploadProgress("Uploading subject media...");

    try {
      const uploadedFiles = [];
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        const mediaType = file.type.startsWith("video/") ? "video" : "image";
        
        const response = await axios.post(`${API}/upload-media?media_type=${mediaType}`, formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });
        uploadedFiles.push(response.data);
      }
      setSubjectFiles([...subjectFiles, ...uploadedFiles]);
      setUploadProgress("");
    } catch (error) {
      console.error("Upload failed:", error);
      alert("Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  const handleAudioUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    setUploadProgress("Uploading audio...");

    try {
      const formData = new FormData();
      formData.append("file", file);
      
      const response = await axios.post(`${API}/upload-media?media_type=audio`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setAudioFile(response.data);
      setUploadProgress("");
    } catch (error) {
      console.error("Audio upload failed:", error);
      alert("Audio upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  const handleGenerate = async () => {
    if (subjectFiles.length === 0) {
      alert("Please upload at least one subject image/video");
      return;
    }
    if (!prompt.trim()) {
      alert("Please describe the dance style");
      return;
    }

    setGenerating(true);

    try {
      const response = await axios.post(`${API}/generate-video`, {
        subject_media_ids: subjectFiles.map(f => f.id),
        audio_file_id: audioFile?.id,
        prompt: prompt,
        duration: duration
      });

      setCurrentVideo(response.data);
      pollVideoStatus(response.data.id);
    } catch (error) {
      console.error("Generation failed:", error);
      const errorMessage = error.response?.data?.detail || "Video generation failed. Please try again.";
      alert(errorMessage);
      setGenerating(false);
    }
  };

  const pollVideoStatus = async (videoId) => {
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${API}/videos/${videoId}`);
        setCurrentVideo(response.data);

        if (response.data.status === "completed" || response.data.status === "failed") {
          clearInterval(interval);
          setGenerating(false);
          loadVideos();
        }
      } catch (error) {
        console.error("Polling failed:", error);
        clearInterval(interval);
        setGenerating(false);
      }
    }, 3000);
  };

  const removeSubjectFile = (id) => {
    setSubjectFiles(subjectFiles.filter(f => f.id !== id));
  };

  return (
    <div className="min-h-screen" style={{ backgroundColor: "#FFF4D2" }}>
      {/* Hero Section */}
      <div className="p-8 md:p-12 lg:p-16 text-center">
        <h1 
          className="text-5xl md:text-6xl font-black tracking-tight uppercase mb-4"
          style={{ fontFamily: "'Bricolage Grotesque', sans-serif", color: "#0A0A0A" }}
          data-testid="app-title"
        >
          DANCING VIDEO GENERATOR
        </h1>
        <p 
          className="text-base md:text-lg font-medium max-w-2xl mx-auto"
          style={{ color: "#404040" }}
        >
          Upload your dogs, people, aliens - add music, describe the dance style, and watch AI bring it to life!
        </p>
      </div>

      {/* Main Content */}
      <div className="px-8 md:px-12 lg:px-16 pb-16 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 md:gap-8">
          {/* Left Column - Uploads and Form */}
          <div className="space-y-6">
            {/* Subject Upload */}
            <div className="neo-card p-6 md:p-8" data-testid="subject-upload-section">
              <h3 
                className="text-2xl md:text-3xl font-bold tracking-tight mb-4"
                style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
              >
                1. UPLOAD SUBJECTS
              </h3>
              <label className="upload-zone block p-12 text-center shadow-[6px_6px_0px_0px_#0A0A0A]">
                <input
                  type="file"
                  multiple
                  accept="image/*,video/*"
                  onChange={handleSubjectUpload}
                  className="hidden"
                  disabled={uploading}
                  data-testid="subject-file-input"
                />
                <div className="text-lg font-bold uppercase" style={{ color: "#0A0A0A" }}>
                  {uploading ? "UPLOADING..." : "📁 CLICK TO UPLOAD"}
                </div>
                <div className="text-sm mt-2" style={{ color: "#404040" }}>
                  Images or videos of dogs, people, aliens, etc.
                </div>
              </label>

              {subjectFiles.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-3" data-testid="uploaded-subjects">
                  {subjectFiles.map((file) => (
                    <div key={file.id} className="relative">
                      {file.media_type === "image" ? (
                        <img
                          src={`${API}/files/${file.id}`}
                          alt="Subject"
                          className="media-preview"
                        />
                      ) : (
                        <video
                          src={`${API}/files/${file.id}`}
                          className="media-preview"
                        />
                      )}
                      <button
                        onClick={() => removeSubjectFile(file.id)}
                        className="absolute -top-2 -right-2 bg-red-500 text-white w-6 h-6 flex items-center justify-center border-2 border-black font-bold"
                        data-testid={`remove-subject-${file.id}`}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Audio Upload */}
            <div className="neo-card p-6 md:p-8" data-testid="audio-upload-section">
              <h3 
                className="text-2xl md:text-3xl font-bold tracking-tight mb-4"
                style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
              >
                2. UPLOAD MUSIC
              </h3>
              <label className="upload-zone block p-12 text-center shadow-[6px_6px_0px_0px_#0A0A0A]">
                <input
                  type="file"
                  accept="audio/*"
                  onChange={handleAudioUpload}
                  className="hidden"
                  disabled={uploading}
                  data-testid="audio-file-input"
                />
                <div className="text-lg font-bold uppercase" style={{ color: "#0A0A0A" }}>
                  {audioFile ? "✓ AUDIO UPLOADED" : uploading ? "UPLOADING..." : "🎵 CLICK TO UPLOAD"}
                </div>
                {audioFile && (
                  <div className="text-sm mt-2" style={{ color: "#404040" }}>
                    {audioFile.original_filename}
                  </div>
                )}
              </label>
            </div>

            {/* Prompt Input */}
            <div className="neo-card p-6 md:p-8" data-testid="prompt-section">
              <h3 
                className="text-2xl md:text-3xl font-bold tracking-tight mb-4"
                style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
              >
                3. DESCRIBE THE VIBE
              </h3>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="E.g., Three dogs wearing sunglasses dancing hip-hop style with confident swagger, spinning and doing the moonwalk..."
                className="w-full px-4 py-3 text-lg border-2 border-black focus:outline-none focus:shadow-[4px_4px_0px_0px_#FFB6C1] transition-shadow"
                style={{ backgroundColor: "white", minHeight: "120px" }}
                disabled={generating}
                data-testid="prompt-textarea"
              />
            </div>

            {/* Generate Button */}
            <button
              onClick={handleGenerate}
              disabled={generating || uploading || subjectFiles.length === 0 || !prompt.trim()}
              className="neo-button w-full px-8 py-4 text-lg font-bold uppercase tracking-wide border-2 border-black"
              style={{
                backgroundColor: generating || uploading || subjectFiles.length === 0 || !prompt.trim() ? "#E5E5E5" : "#FFB6C1",
                color: "#0A0A0A",
                boxShadow: "4px 4px 0px 0px #0A0A0A",
                cursor: generating || uploading || subjectFiles.length === 0 || !prompt.trim() ? "not-allowed" : "pointer"
              }}
              data-testid="generate-button"
            >
              {generating ? "🎬 GENERATING VIDEO..." : "🚀 GENERATE VIDEO"}
            </button>

            {uploadProgress && (
              <div className="text-center font-bold" style={{ color: "#0A0A0A" }}>
                {uploadProgress}
              </div>
            )}
          </div>

          {/* Right Column - Video Preview */}
          <div>
            <div className="neo-card p-6 md:p-8" data-testid="video-preview-section">
              <h3 
                className="text-2xl md:text-3xl font-bold tracking-tight mb-4"
                style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
              >
                VIDEO PREVIEW
              </h3>

              {currentVideo && currentVideo.status === "generating" && (
                <div 
                  className="p-12 border-2 border-black text-center"
                  style={{ backgroundColor: "#FFD700" }}
                  data-testid="generating-status"
                >
                  <div className="overflow-hidden">
                    <div className="marquee text-xl font-bold uppercase">
                      🎬 DROPPING BEATS... CHOREOGRAPHING... RAPPING... 🎬
                    </div>
                  </div>
                  <p className="mt-4 text-sm font-semibold">This may take 2-5 minutes...</p>
                </div>
              )}

              {currentVideo && currentVideo.status === "completed" && (
                <div data-testid="completed-video">
                  <video
                    controls
                    className="video-player"
                    src={`${API}/video-file/${currentVideo.id}`}
                    data-testid="video-player"
                  />
                  <div className="mt-4 p-4 border-2 border-black" style={{ backgroundColor: "#98FB98" }}>
                    <p className="font-bold">✅ VIDEO COMPLETE!</p>
                    <p className="text-sm mt-1">{currentVideo.prompt}</p>
                  </div>
                </div>
              )}

              {currentVideo && currentVideo.status === "failed" && (
                <div 
                  className="p-8 border-2 border-black text-center"
                  style={{ backgroundColor: "#FFB6C1" }}
                  data-testid="failed-status"
                >
                  <p className="font-bold text-xl">❌ GENERATION FAILED</p>
                  <p className="text-sm mt-2">{currentVideo.error_message || "Something went wrong"}</p>
                </div>
              )}

              {!currentVideo && (
                <div 
                  className="p-12 border-4 border-dashed border-black text-center"
                  style={{ backgroundColor: "#E0F2FE", minHeight: "300px" }}
                  data-testid="empty-preview"
                >
                  <div className="text-6xl mb-4">🎥</div>
                  <p className="text-lg font-bold uppercase">YOUR VIDEO WILL APPEAR HERE</p>
                </div>
              )}
            </div>

            {/* Previous Videos */}
            {videos.length > 0 && (
              <div className="mt-6 neo-card p-6" data-testid="previous-videos">
                <h4 className="text-xl font-bold mb-4" style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>
                  PREVIOUS GENERATIONS
                </h4>
                <div className="space-y-3">
                  {videos.slice(0, 5).map((video) => (
                    <div
                      key={video.id}
                      className="p-3 border-2 border-black cursor-pointer hover:bg-gray-50"
                      onClick={() => setCurrentVideo(video)}
                      data-testid={`video-history-${video.id}`}
                    >
                      <div className="flex justify-between items-start">
                        <p className="text-sm font-semibold flex-1">{video.prompt.substring(0, 60)}...</p>
                        <span 
                          className="px-2 py-1 text-xs font-bold border border-black ml-2"
                          style={{
                            backgroundColor: video.status === "completed" ? "#98FB98" : video.status === "failed" ? "#FFB6C1" : "#FFD700"
                          }}
                        >
                          {video.status.toUpperCase()}
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