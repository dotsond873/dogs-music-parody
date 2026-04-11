import { useState, useEffect } from "react";
import "@/App.css";
import axios from "axios";
import { useVideoGeneration } from "./hooks/useVideoGeneration";
import { useFileUpload } from "./hooks/useFileUpload";
import { UploadSection, MediaPreviewGrid } from "./components/UploadSection";
import { VideoPreview } from "./components/VideoPreview";
import { VideoHistory } from "./components/VideoHistory";

function App() {
  const [subjectFiles, setSubjectFiles] = useState([]);
  const [audioFile, setAudioFile] = useState(null);
  const [prompt, setPrompt] = useState("");
  const duration = 30;

  const { uploading, uploadProgress, uploadFiles } = useFileUpload();
  const { 
    videos, 
    currentVideo, 
    generating, 
    loadVideos, 
    generateVideo, 
    setCurrentVideo 
  } = useVideoGeneration();

  useEffect(() => {
    loadVideos();
  }, [loadVideos]);

  const handleSubjectUpload = async (e) => {
    const files = Array.from(e.target.files);
    const uploaded = await uploadFiles(files, "image");
    if (uploaded.length > 0) {
      setSubjectFiles([...subjectFiles, ...uploaded]);
    }
  };

  const handleAudioUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const uploaded = await uploadFiles([file], "audio");
    if (uploaded.length > 0) {
      setAudioFile(uploaded[0]);
    }
  };

  const handleYouTubeAudio = async (youtubeUrl) => {
    if (!youtubeUrl) return;
    
    setUploadProgress("Extracting audio from YouTube...");
    
    try {
      const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;
      const API = `${BACKEND_URL}/api`;
      
      const response = await axios.post(`${API}/youtube-audio`, {
        youtube_url: youtubeUrl
      });

      setAudioFile(response.data);
      setUploadProgress("");
      alert(`✓ Audio extracted: ${response.data.original_filename}`);
    } catch (error) {
      console.error('YouTube audio extraction failed:', error);
      alert('Failed to extract audio from YouTube. Please check the URL and try again.');
      setUploadProgress("");
    }
  };

  const handleGenerate = () => {
    if (subjectFiles.length === 0) {
      alert("Please upload at least one subject image/video");
      return;
    }
    if (!prompt.trim()) {
      alert("Please describe the dance style");
      return;
    }

    const subjectIds = subjectFiles.map(f => f.id);
    const audioId = audioFile?.id;
    generateVideo(subjectIds, audioId, prompt, duration);
  };

  const removeSubjectFile = (id) => {
    setSubjectFiles(subjectFiles.filter(f => f.id !== id));
  };

  const isGenerateDisabled = generating || uploading || subjectFiles.length === 0 || !prompt.trim();

  return (
    <div className="min-h-screen" style={{ backgroundColor: "#FFF4D2" }}>
      {/* Hero Section */}
      <div className="p-8 md:p-12 lg:p-16 text-center">
        <h1 
          className="text-5xl md:text-6xl font-black tracking-tight uppercase mb-4"
          style={{ fontFamily: "'Bricolage Grotesque', sans-serif", color: "#0A0A0A" }}
          data-testid="app-title"
        >
          Dancing Dave's Swamp Donkeys and Spundunnits
        </h1>
        <p 
          className="text-base md:text-lg font-medium max-w-2xl mx-auto"
          style={{ color: "#404040" }}
        >
          Upload your swamp donkeys, spundunnits, or whatever critters you got - add music, describe the dance style, and watch AI bring it to life!
        </p>
      </div>

      {/* Main Content */}
      <div className="px-8 md:px-12 lg:px-16 pb-16 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 md:gap-8">
          {/* Left Column - Uploads and Form */}
          <div className="space-y-6">
            {/* Subject Upload */}
            <div>
              <div className="neo-card p-6 md:p-8" data-testid="subject-upload-section">
                <h3 
                  className="text-2xl md:text-3xl font-bold tracking-tight mb-4"
                  style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
                >
                  1. UPLOAD SUBJECTS
                </h3>
                
                <div className="mb-3 p-3 border-2 border-black" style={{ backgroundColor: "#98FB98" }}>
                  <p className="text-xs font-bold uppercase">
                    ✨ Your uploaded image will be used as the starting frame! The AI will animate YOUR dogs/subjects, not random ones.
                  </p>
                </div>
                
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
                    Images or videos of swamp donkeys, spundunnits, or whatever!
                  </div>
                </label>
              </div>
              <MediaPreviewGrid 
                files={subjectFiles} 
                onRemove={removeSubjectFile}
              />
            </div>

            {/* Audio Upload */}
            <div className="neo-card p-6 md:p-8" data-testid="audio-upload-section">
              <h3 
                className="text-2xl md:text-3xl font-bold tracking-tight mb-4"
                style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
              >
                2. UPLOAD MUSIC
              </h3>
              
              <div className="mb-3 p-3 border-2 border-black" style={{ backgroundColor: "#FFD700" }}>
                <p className="text-xs font-bold uppercase">
                  ⚠️ Your music will be added to the generated video!
                </p>
              </div>
              
              {/* YouTube URL Input */}
              <div className="mb-4">
                <input
                  type="text"
                  placeholder="Paste YouTube URL here (e.g., youtube.com/watch?v=...)"
                  className="w-full px-4 py-3 text-base border-2 border-black focus:outline-none focus:shadow-[4px_4px_0px_0px_#FFB6C1] transition-shadow mb-2"
                  style={{ backgroundColor: "white" }}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && e.target.value.trim()) {
                      handleYouTubeAudio(e.target.value.trim());
                      e.target.value = '';
                    }
                  }}
                  disabled={uploading}
                  data-testid="youtube-url-input"
                />
                <p className="text-xs font-semibold uppercase" style={{ color: "#404040" }}>
                  Press Enter to extract audio from YouTube
                </p>
              </div>

              <div className="text-center my-4 font-bold" style={{ color: "#0A0A0A" }}>
                OR
              </div>

              {/* File Upload */}
              <UploadSection
                title=""
                subtitle="Upload your own audio file (MP3, WAV, etc.)"
                accept="audio/*"
                multiple={false}
                onUpload={handleAudioUpload}
                uploading={uploading}
                uploadedFile={audioFile}
                testId="audio-file-upload"
              />
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
                placeholder="E.g., The three dogs are now wearing hip-hop clothing with baggy pants and gold chains. They dance with swagger, spinning and doing the moonwalk to the beat..."
                className="w-full px-4 py-3 text-lg border-2 border-black focus:outline-none focus:shadow-[4px_4px_0px_0px_#FFB6C1] transition-shadow"
                style={{ backgroundColor: "white", minHeight: "120px" }}
                disabled={generating}
                data-testid="prompt-textarea"
              />
              <p className="text-xs mt-2 font-semibold" style={{ color: "#404040" }}>
                💡 Describe how your subjects should move and what they should wear. The AI will add the clothing and animate them!
              </p>
            </div>

            {/* Generate Button */}
            <button
              onClick={handleGenerate}
              disabled={isGenerateDisabled}
              className="neo-button w-full px-8 py-4 text-lg font-bold uppercase tracking-wide border-2 border-black"
              style={{
                backgroundColor: isGenerateDisabled ? "#E5E5E5" : "#FFB6C1",
                color: "#0A0A0A",
                boxShadow: "4px 4px 0px 0px #0A0A0A",
                cursor: isGenerateDisabled ? "not-allowed" : "pointer"
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
            <VideoPreview currentVideo={currentVideo} />
            <VideoHistory videos={videos} onVideoClick={setCurrentVideo} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
