'use client';

import { FileUpload } from './file-upload';

interface InputPanelProps {
  text: string;
  onTextChange: (text: string) => void;
  onUpload: (file: File) => Promise<{ filename: string; size_kb: number }>;
}

export function InputPanel({ text, onTextChange, onUpload }: InputPanelProps) {
  return (
    <div className="flex flex-col h-full border-r border-[hsl(230,20%,15%)]">
      <div className="px-4 py-3 bg-[hsl(230,40%,8%)] border-b border-[hsl(230,20%,15%)] text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider">
        Screenplay
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <FileUpload
          accept=".docx"
          label="Drop or upload a .docx screenplay"
          hint="Word documents only"
          onUpload={onUpload}
        />
        <textarea
          className="w-full h-[calc(100%-80px)] min-h-[200px] bg-[hsl(230,40%,6%)] border border-[hsl(230,20%,15%)] rounded-md p-3 text-sm text-[hsl(var(--foreground))] resize-none focus:outline-none focus:border-[hsl(var(--primary))] font-mono leading-relaxed"
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          placeholder="Upload a screenplay to preview and edit it here..."
        />
      </div>
    </div>
  );
}
