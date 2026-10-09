import React, { useState } from 'react';
import { ICONS } from '../constants';

interface DropZoneProps {
  id: string;
  onFile: (file: File) => void;
  hint?: string;
}

const DropZone: React.FC<DropZoneProps> = ({ id, onFile, hint = 'MP4, MOV, MKV, AVI, WebM' }) => {
  const [isDragging, setIsDragging] = useState(false);

  const acceptFile = (f: File) => {
    if (f.type.startsWith('video/') || /\.(mp4|mov|mkv|avi|webm)$/i.test(f.name)) {
      onFile(f);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) acceptFile(e.target.files[0]);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragging(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) acceptFile(dropped);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      document.getElementById(id)?.click();
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Upload video file. Press Enter or Space to browse, or drag and drop a file here."
      onClick={() => document.getElementById(id)?.click()}
      onKeyDown={handleKeyDown}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`w-full h-full border-2 border-dashed rounded-2xl transition-all flex flex-col items-center justify-center text-center cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)] py-16 md:py-24 px-8 space-y-5 ${
        isDragging ? 'border-brand bg-brand-soft' : 'border-edge-strong hover:border-brand/60 hover:bg-brand-soft/40'
      }`}
    >
      <input type="file" id={id} className="hidden" accept="video/*" onChange={handleFileChange} />
      <div className="p-4 rounded-full bg-edge/70 text-ink-faint flex items-center justify-center transition-colors">
        <span className="scale-150"><ICONS.Video /></span>
      </div>
      <div>
        <p className="font-semibold text-ink-soft text-lg">Drop your video here</p>
        <p className="text-sm text-ink-faint mt-1">{hint}</p>
      </div>
    </div>
  );
};

export default DropZone;
