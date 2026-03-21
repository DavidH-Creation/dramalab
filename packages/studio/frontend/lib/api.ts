import type { InitResult, UploadResult } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export async function uploadFile(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  return res.json();
}

export async function initPlugin(
  name: string,
  inputText: string,
  criteriaText: string,
  config: Record<string, unknown>,
): Promise<InitResult> {
  const res = await fetch(`${API_BASE}/plugins/${name}/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input_text: inputText, criteria_text: criteriaText, config }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export async function stopPlugin(name: string, sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/plugins/${name}/${sessionId}/stop`, { method: 'POST' });
}

export async function getStatus(name: string, sessionId: string) {
  const res = await fetch(`${API_BASE}/plugins/${name}/${sessionId}/status`);
  return res.json();
}

export async function getText(name: string, sessionId: string): Promise<string> {
  const res = await fetch(`${API_BASE}/plugins/${name}/${sessionId}/text`);
  const data = await res.json();
  return data.text;
}

export async function exportDocx(name: string, sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/plugins/${name}/${sessionId}/export`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'improved.docx';
  a.click();
  URL.revokeObjectURL(url);
}

export function getStreamUrl(name: string, sessionId: string): string {
  return `${API_BASE}/plugins/${name}/${sessionId}/run`;
}
