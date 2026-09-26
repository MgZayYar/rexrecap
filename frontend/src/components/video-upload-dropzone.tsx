"use client";

import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { ProjectPicker } from "@/components/project-picker";

const ALLOWED_EXTENSIONS = ["mp4", "mov", "mkv", "avi"];

function isAllowedVideo(file: File) {
  return ALLOWED_EXTENSIONS.includes(file.name.split(".").pop()?.toLowerCase() ?? "");
}

export function VideoUploadDropzone() {
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);

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

  function upload() {
    if (!file || isUploading) return;
    setIsUploading(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    if (projectId !== null) form.append("project_id", String(projectId));
    const request = new XMLHttpRequest();
    request.open("POST", "/api/videos/upload");
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) setProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onerror = () => {
      setError("The upload could not be completed. Please try again.");
      setIsUploading(false);
    };
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        router.push("/dashboard");
        router.refresh();
        return;
      }
      try {
        setError(JSON.parse(request.responseText).detail ?? "Unable to upload video.");
      } catch {
        setError("Unable to upload video.");
      }
      setIsUploading(false);
    };
    request.send(form);
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <input ref={inputRef} className="sr-only" type="file" accept=".mp4,.mov,.mkv,.avi,video/mp4,video/quicktime,video/x-matroska,video/x-msvideo" onChange={handleChange} />
      <div onDrop={handleDrop} onDragOver={(event) => event.preventDefault()} onClick={() => inputRef.current?.click()} className="cursor-pointer rounded-lg border-2 border-dashed border-slate-300 p-10 text-center transition hover:border-slate-500">
        <p className="font-medium">Drag a video here, or click to browse</p>
        <p className="mt-2 text-sm text-slate-600">MP4, MOV, MKV, or AVI</p>
      </div>
      {file && <p className="mt-4 text-sm text-slate-700">Selected: <span className="font-medium">{file.name}</span></p>}
      <label className="mt-4 flex items-center gap-2 text-sm text-slate-600">
        Project
        <ProjectPicker value={projectId} onChange={setProjectId} disabled={isUploading} ariaLabel="Project for this upload" />
      </label>
      {isUploading && <div className="mt-4" aria-live="polite"><div className="mb-1 flex justify-between text-sm"><span>Uploading</span><span>{progress}%</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-slate-900 transition-all" style={{ width: `${progress}%` }} /></div></div>}
      {error && <p className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</p>}
      <Button className="mt-6 w-full" type="button" disabled={!file || isUploading} onClick={upload}>{isUploading ? "Uploading…" : "Upload video"}</Button>
    </section>
  );
}
