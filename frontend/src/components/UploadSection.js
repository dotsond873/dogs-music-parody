import React from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = `${BACKEND_URL}/api`;

export const UploadSection = ({ 
  title, 
  subtitle, 
  accept, 
  multiple = false, 
  onUpload, 
  uploading, 
  uploadedFile,
  testId 
}) => {
  return (
    <div className="neo-card p-6 md:p-8" data-testid={testId}>
      <h3 
        className="text-2xl md:text-3xl font-bold tracking-tight mb-4"
        style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
      >
        {title}
      </h3>
      <label className="upload-zone block p-12 text-center shadow-[6px_6px_0px_0px_#0A0A0A]">
        <input
          type="file"
          multiple={multiple}
          accept={accept}
          onChange={onUpload}
          className="hidden"
          disabled={uploading}
          data-testid={`${testId}-input`}
        />
        <div className="text-lg font-bold uppercase" style={{ color: "#0A0A0A" }}>
          {uploading ? "UPLOADING..." : uploadedFile ? "✓ UPLOADED" : "📁 CLICK TO UPLOAD"}
        </div>
        <div className="text-sm mt-2" style={{ color: "#404040" }}>
          {subtitle}
        </div>
        {uploadedFile && (
          <div className="text-sm mt-2 font-semibold" style={{ color: "#0A0A0A" }}>
            {uploadedFile.original_filename}
          </div>
        )}
      </label>
    </div>
  );
};

export const MediaPreviewGrid = ({ files, onRemove }) => {
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
  const API = `${BACKEND_URL}/api`;
  
  if (files.length === 0) return null;

  return (
    <div className="mt-4 flex flex-wrap gap-3" data-testid="uploaded-subjects">
      {files.map((file) => (
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
            onClick={() => onRemove(file.id)}
            className="absolute -top-2 -right-2 bg-red-500 text-white w-6 h-6 flex items-center justify-center border-2 border-black font-bold"
            data-testid={`remove-subject-${file.id}`}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
};