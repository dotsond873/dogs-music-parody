import { useState } from 'react';
import axios from 'axios';

const getApiUrl = () => {
  const backendUrl = process.env.REACT_APP_BACKEND_URL || window.location.origin;
  return `${backendUrl}/api`;
};

export const useFileUpload = () => {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');

  const uploadFiles = async (files, mediaType) => {
    setUploading(true);
    setUploadProgress(`Uploading ${mediaType}...`);

    try {
      const uploadedFiles = [];
      for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        const type = file.type.startsWith('video/') ? 'video' : mediaType;
        
        const response = await axios.post(`${getApiUrl()}/upload-media?media_type=${type}`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        uploadedFiles.push(response.data);
      }
      setUploadProgress('');
      return uploadedFiles;
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed. Please try again.');
      return [];
    } finally {
      setUploading(false);
    }
  };

  return {
    uploading,
    uploadProgress,
    uploadFiles
  };
};
