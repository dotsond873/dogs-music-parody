import React from 'react';

const getStatusColor = (status) => {
  if (status === 'completed') return '#98FB98';
  if (status === 'failed') return '#FFB6C1';
  return '#FFD700';
};

export const VideoHistory = ({ videos, onVideoClick }) => {
  if (videos.length === 0) return null;

  return (
    <div className="mt-6 neo-card p-6" data-testid="previous-videos">
      <h4 className="text-xl font-bold mb-4" style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>
        PREVIOUS GENERATIONS
      </h4>
      <div className="space-y-3">
        {videos.slice(0, 5).map((video) => (
          <div
            key={video.id}
            className="p-3 border-2 border-black cursor-pointer hover:bg-gray-50"
            onClick={() => onVideoClick(video)}
            data-testid={`video-history-${video.id}`}
          >
            <div className="flex justify-between items-start">
              <p className="text-sm font-semibold flex-1">
                {video.prompt.substring(0, 60)}...
              </p>
              <span 
                className="px-2 py-1 text-xs font-bold border border-black ml-2"
                style={{ backgroundColor: getStatusColor(video.status) }}
              >
                {video.status.toUpperCase()}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};