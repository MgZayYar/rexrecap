"use client";

import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { ProjectPicker } from "@/components/project-picker";
import { apiGet, toMessage } from "@/lib/api-client";
import { formatBytes, QuotaInfo, uploadFileResumable } from "@/lib/resumable-upload";

const ALLOWED_EXTENSIONS = ["mp4", "mov", "mkv", "avi"];

function isAllowedVideo(file: File) {
  return ALLOWED_EXTENSIONS.includes(file.name.split(".").pop()?.toLowerCase() ?? "");
}

export function VideoUploadDropzone() {
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [quota, setQuota] = useState<QuotaInfo | null>(null);

  useEffect(() => {
    apiGet<QuotaInfo>("/api/videos/quota").then(setQuota).catch(() => undefined);
    return () => abortRef.current?.abort();
  }, []);

  function selectFile(candidate?: File) {
    setError(null);
    setProgress(0);
    if (!candidate) return;
    if (!isAllowedVideo(candidate)) {
      setFile(null);
      setError("Choose an MP4, MOV, MKV, or AVI video.");
      return;
    }
    setFile(candidate);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    selectFile(event.dataTransfer.files[0]);
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.target.files?.[0]);
  }

  async function upload() {
    if (!file || isUploading) return;
    setIsUploading(true);
    setError(null);
    setProgress(0);
    abortRef.current = new AbortController();
    try {
      await uploadFileResumable(file, projectId, (fraction) => {
        setProgress(Math.round(fraction * 100));
      }, abortRef.current.signal);
      router.push("/dashboard");
      router.refresh();
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        setError("Upload cancelled.");
      } else {
        setError(toMessage(error, "The upload could not be completed. It will resume from where it stopped if you try again."));
      }
      setIsUploading(false);
    }
  }

  function cancel() {
    abortRef.current?.abort();
  }

  const quotaPercent = quota && quota.quota_bytes > 0
    ? Math.min(100, Math.round((quota.used_bytes / quota.quota_bytes) * 100))
    : 0;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <input ref={inputRef} className="sr-only" type="file" accept=".mp4,.mov,.mkv,.avi,video/mp4,video/quicktime,video/x-matroska,video/x-msvideo" onChange={handleChange} />
      <div onDrop={handleDrop} onDragOver={(event) => event.preventDefault()} onClick={() => inputRef.current?.click()} className="cursor-pointer rounded-lg border-2 border-dashed border-slate-300 p-10 text-center transition hover:border-slate-500">
        <p className="font-medium">Drag a video here, or click to browse</p>
        <p className="mt-2 text-sm text-slate-600">MP4, MOV, MKV, or AVI — uploads resume automatically if interrupted</p>
      </div>
      {file && <p className="mt-4 text-sm text-slate-700">Selected: <span className="font-medium">{file.name}</span> ({formatBytes(file.size)})</p>}
      <label className="mt-4 flex items-center gap-2 text-sm text-slate-600">
        Project
        <ProjectPicker value={projectId} onChange={setProjectId} disabled={isUploading} ariaLabel="Project for this upload" />
      </label>
      {quota && (
        <div className="mt-4 text-sm text-slate-600" aria-live="polite">
          <div className="mb-1 flex justify-between">
            <span>Storage</span>
            <span>{formatBytes(quota.used_bytes)} of {formatBytes(quota.quota_bytes)} used</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-200">
            <div className="h-full bg-slate-500 transition-all" style={{ width: `${quotaPercent}%` }} />
          </div>
        </div>
      )}
      {isUploading && <div className="mt-4" aria-live="polite"><div className="mb-1 flex justify-between text-sm"><span>Uploading</span><span>{progress}%</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-slate-900 transition-all" style={{ width: `${progress}%` }} /></div></div>}
      {error && <p className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</p>}
      <div className="mt-6 flex gap-2">
        <Button className="flex-1" type="button" disabled={!file || isUploading} onClick={upload}>{isUploading ? "Uploading…" : "Upload video"}</Button>
        {isUploading && <Button type="button" variant="outline" onClick={cancel}>Cancel</Button>}
      </div>
    </section>
  );
}
