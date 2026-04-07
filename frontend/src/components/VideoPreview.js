import React from 'react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const GeneratingStatus = () => (
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
);

const CompletedVideo = ({ videoId, prompt }) => (
  <div data-testid="completed-video">
    <video
      controls
      className="video-player"
      src={`${API}/video-file/${videoId}`}
      data-testid="video-player"
    />
    <div className="mt-4 p-4 border-2 border-black" style={{ backgroundColor: "#98FB98" }}>
      <p className="font-bold">✅ VIDEO COMPLETE!</p>
      <p className="text-sm mt-1">{prompt}</p>
    </div>
  </div>
);

const FailedStatus = ({ errorMessage }) => (
  <div 
    className="p-8 border-2 border-black text-center"
    style={{ backgroundColor: "#FFB6C1" }}
    data-testid="failed-status"
  >
    <p className="font-bold text-xl">❌ GENERATION FAILED</p>
    <p className="text-sm mt-2">{errorMessage || "Something went wrong"}</p>
  </div>
);

const EmptyPreview = () => (
  <div 
    className="p-12 border-4 border-dashed border-black text-center"
    style={{ backgroundColor: "#E0F2FE", minHeight: "300px" }}
    data-testid="empty-preview"
  >
    <div className="text-6xl mb-4">🎥</div>
    <p className="text-lg font-bold uppercase">YOUR VIDEO WILL APPEAR HERE</p>
  </div>
);

export const VideoPreview = ({ currentVideo }) => {
  const renderPreview = () => {
    if (!currentVideo) {
      return <EmptyPreview />;
    }

    if (currentVideo.status === 'generating') {
      return <GeneratingStatus />;
    }

    if (currentVideo.status === 'completed') {
      return <CompletedVideo videoId={currentVideo.id} prompt={currentVideo.prompt} />;
    }

    if (currentVideo.status === 'failed') {
      return <FailedStatus errorMessage={currentVideo.error_message} />;
    }

    return <EmptyPreview />;
  };

  return (
    <div className="neo-card p-6 md:p-8" data-testid="video-preview-section">
      <h3 
        className="text-2xl md:text-3xl font-bold tracking-tight mb-4"
        style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
      >
        VIDEO PREVIEW
      </h3>
      {renderPreview()}
    </div>
  );
};