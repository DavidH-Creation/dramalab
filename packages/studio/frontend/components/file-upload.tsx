'use client';

import { Upload, X } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';

interface FileUploadProps {
  accept: string;
  label: string;
  hint?: string;
  onUpload: (file: File) => Promise<{ filename: string; size_kb: number }>;
  compact?: boolean;
}

export function FileUpload({ accept, label, hint, onUpload, compact }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<{ name: string; size: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  const handleFile = useCallback(
    async (f: File) => {
      const result = await onUpload(f);
      setFile({ name: result.filename, size: result.size_kb });
    },
    [onUpload],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
    },
    [handleFile],
  );

  if (file) {
    return (
      <div className="bg-[hsl(230,30%,12%)] border border-[hsl(230,20%,20%)] rounded-md px-3 py-2 flex items-center gap-2 mb-3">
        <span className="text-xs text-[hsl(var(--muted-foreground))] flex-1 truncate">{file.name}</span>
        <span className="text-xs text-[hsl(230,20%,30%)]">{file.size} KB</span>
        <button onClick={() => setFile(null)} className="text-red-400 hover:text-red-300">
          <X className="w-3 h-3" />
        </button>
      </div>
    );
  }

  return (
    <div
      className={`border-2 border-dashed rounded-md text-center cursor-pointer transition-colors mb-3 ${
        dragging ? 'border-[hsl(var(--primary))]' : 'border-[hsl(230,20%,20%)]'
      } hover:border-[hsl(var(--primary))] ${compact ? 'p-3' : 'p-5'}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <Upload className={`mx-auto text-[hsl(var(--muted-foreground))] ${compact ? 'w-4 h-4 mb-1' : 'w-7 h-7 mb-2'}`} />
      <div className={`text-[hsl(var(--muted-foreground))] ${compact ? 'text-[10px]' : 'text-xs'}`}>{label}</div>
      {hint && <div className="text-[10px] text-[hsl(230,20%,25%)] mt-1">{hint}</div>}
      <input ref={inputRef} type="file" accept={accept} className="hidden" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
    </div>
  );
}
