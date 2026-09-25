import { redirect } from "next/navigation";

import { VideoUploadDropzone } from "@/components/video-upload-dropzone";
import { getServerSession } from "@/lib/server-auth";

export default async function UploadPage() {
  if (!(await getServerSession())) redirect("/login");

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col justify-center p-6">
      <div className="mb-8"><p className="text-sm font-medium text-slate-600">RexCrop</p><h1 className="mt-2 text-3xl font-semibold">Upload a video</h1><p className="mt-2 text-slate-600">Your upload will be saved securely to your workspace.</p></div>
      <VideoUploadDropzone />
    </main>
  );
}
