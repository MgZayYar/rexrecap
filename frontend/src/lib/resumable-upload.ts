/**
 * Resumable chunked uploads against the Next.js /api/videos/uploads proxy.
 *
 * The server is the source of truth for the byte offset: every chunk is sent
 * with the Upload-Offset we believe is current, and a 409 tells us the server
 * has a different offset (e.g. a previous chunk actually landed despite a
 * dropped response), in which case we re-read the session and continue.
 */

import { ApiError, apiFetch, apiPost } from "@/lib/api-client";

export interface UploadSessionInfo {
  id: string;
  filename: string;
  content_type: string;
  total_bytes: number;
  received_bytes: number;
  project_id: number | null;
  status: string;
}

export interface QuotaInfo {
  quota_bytes: number;
  used_bytes: number;
  available_bytes: number;
}

const CHUNK_SIZE = 8 * 1024 * 1024;
const MAX_CHUNK_RETRIES = 4;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function uploadOneChunk(sessionId: string, offset: number, chunk: Blob): Promise<UploadSessionInfo> {
  return apiFetch<UploadSessionInfo>(`/api/videos/uploads/${sessionId}`, {
    method: "PATCH",
    headers: { "Upload-Offset": String(offset), "Content-Type": "application/octet-stream" },
    body: chunk,
  });
}

/**
 * Upload a file in chunks, resuming from the server offset on transient
 * failures. Calls onProgress with a 0..1 fraction. Throws on quota,
 * validation, or unrecoverable errors.
 */
export async function uploadFileResumable(
  file: File,
  projectId: number | null,
  onProgress: (fraction: number) => void,
  signal: AbortSignal,
): Promise<unknown> {
  const session = await apiPost<UploadSessionInfo>("/api/videos/uploads", {
    filename: file.name,
    content_type: file.type || "video/mp4",
    total_bytes: file.size,
    project_id: projectId,
  });
  let offset = session.received_bytes;
  onProgress(file.size === 0 ? 1 : offset / file.size);

  while (offset < file.size) {
    if (signal.aborted) {
      await apiFetch(`/api/videos/uploads/${session.id}`, { method: "DELETE" }).catch(() => undefined);
      throw new DOMException("Upload cancelled", "AbortError");
    }
    const chunk = file.slice(offset, Math.min(offset + CHUNK_SIZE, file.size));
    let attempt = 0;
    for (;;) {
      try {
        const updated = await uploadOneChunk(session.id, offset, chunk);
        offset = updated.received_bytes;
        onProgress(offset / file.size);
        break;
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          // Offset drifted (e.g. a chunk landed but its response was lost):
          // re-read the true offset and continue from there.
          const current = await apiFetch<UploadSessionInfo>(`/api/videos/uploads/${session.id}`);
          offset = current.received_bytes;
          onProgress(offset / file.size);
          break;
        }
        attempt += 1;
        if (attempt >= MAX_CHUNK_RETRIES) throw error;
        await sleep(500 * 2 ** (attempt - 1));
      }
    }
  }

  return apiPost(`/api/videos/uploads/${session.id}/complete`);
}

/** Human-readable byte size, e.g. 8.4 GB. */
export function formatBytes(bytes: number): string {
  if (bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** index;
  return `${value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[index]}`;
}
