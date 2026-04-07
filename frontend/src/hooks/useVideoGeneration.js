import { useState, useCallback } from 'react';
import axios from 'axios';

const getApiUrl = () => {
  const backendUrl = process.env.REACT_APP_BACKEND_URL || window.location.origin;
  return `${backendUrl}/api`;
};

export const useVideoGeneration = () => {
  const [videos, setVideos] = useState([]);
  const [currentVideo, setCurrentVideo] = useState(null);
  const [generating, setGenerating] = useState(false);

  const loadVideos = useCallback(async () => {
    try {
      const response = await axios.get(`${getApiUrl()}/videos`);
      setVideos(response.data);
    } catch (error) {
      console.error('Failed to load videos:', error);
    }
  }, []);

  const pollVideoStatus = useCallback((videoId) => {
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${getApiUrl()}/videos/${videoId}`);
        setCurrentVideo(response.data);

        if (response.data.status === 'completed' || response.data.status === 'failed') {
          clearInterval(interval);
          setGenerating(false);
          loadVideos();
        }
      } catch (error) {
        console.error('Polling failed:', error);
        clearInterval(interval);
        setGenerating(false);
      }
    }, 3000);
  }, [loadVideos]);

  const generateVideo = useCallback(async (subjectFileIds, audioFileId, prompt, duration) => {
    setGenerating(true);

    try {
      const response = await axios.post(`${getApiUrl()}/generate-video`, {
        subject_media_ids: subjectFileIds,
        audio_file_id: audioFileId,
        prompt: prompt,
        duration: duration
      });

      setCurrentVideo(response.data);
      pollVideoStatus(response.data.id);
    } catch (error) {
      console.error('Generation failed:', error);
      const errorMessage = error.response?.data?.detail || 'Video generation failed. Please try again.';
      alert(errorMessage);
      setGenerating(false);
    }
  }, [pollVideoStatus]);

  return {
    videos,
    currentVideo,
    generating,
    loadVideos,
    generateVideo,
    setCurrentVideo
  };
};
