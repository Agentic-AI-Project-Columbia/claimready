/**
 * Backend API client.
 *
 * Backend URL is read from NEXT_PUBLIC_BACKEND_URL at build time.
 * On the deployed Cloud Run frontend service it points at the backend's
 * Cloud Run URL; in local dev it points at http://localhost:8000.
 */

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000';

const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? '';

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (API_KEY) h['X-API-Key'] = API_KEY;
  return h;
}

export type Intake = Record<string, any>;

export async function createCase(intake: Intake): Promise<{ case_id: string }> {
  const res = await fetch(`${BACKEND_URL}/api/case`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(intake),
  });
  if (!res.ok) throw new Error(`createCase failed: ${res.status}`);
  return res.json();
}

export async function prepareCase(): Promise<{ case_id: string }> {
  const res = await fetch(`${BACKEND_URL}/api/case/prepare`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`prepareCase failed: ${res.status}`);
  return res.json();
}

export async function startCase(
  caseId: string,
  intake: Intake,
): Promise<{ case_id: string }> {
  const res = await fetch(`${BACKEND_URL}/api/case/${caseId}/start`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(intake),
  });
  if (!res.ok) throw new Error(`startCase failed: ${res.status}`);
  return res.json();
}

export async function uploadEvidence(
  caseId: string,
  files: File[],
): Promise<{ items: Array<{ filename: string; mime_type: string; size: number; text: string }> }> {
  const fd = new FormData();
  files.forEach((f) => fd.append('files', f));
  const res = await fetch(`${BACKEND_URL}/api/case/${caseId}/evidence`, {
    method: 'POST',
    body: fd,
  });
  if (!res.ok) throw new Error(`uploadEvidence failed: ${res.status}`);
  return res.json();
}

export function caseEventsURL(caseId: string): string {
  // Choose ws/wss to match the http/https scheme of the backend.
  const url = new URL(BACKEND_URL);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = `/api/case/${caseId}/events`;
  return url.toString();
}

export function pdfURL(caseId: string): string {
  return `${BACKEND_URL}/api/case/${caseId}/pdf`;
}

export interface DemoScenario {
  title: string;
  blurb: string;
  intake: Record<string, any>;
  evidence_filenames: string[];
}

export async function getDemoScenario(): Promise<DemoScenario> {
  const res = await fetch(`${BACKEND_URL}/api/demo/scenario`);
  if (!res.ok) throw new Error(`getDemoScenario failed: ${res.status}`);
  return res.json();
}

export async function runDemo(): Promise<{ case_id: string; title: string; blurb: string }> {
  const res = await fetch(`${BACKEND_URL}/api/demo/run`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`runDemo failed: ${res.status}`);
  return res.json();
}
