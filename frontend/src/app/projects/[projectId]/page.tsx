import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { LogoutButton } from "@/components/logout-button";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/feedback";
import { backendFetchWithAuth } from "@/lib/server-backend";
import { getServerSession } from "@/lib/server-auth";
import { formatFileSize, type Project, type Video } from "@/lib/video";

export default async function ProjectDetailPage({ params }: { params: Promise<{ projectId: string }> }) {
  const session = await getServerSession();
  if (!session) redirect("/login");
  const { projectId } = await params;
  const [projectResponse, videosResponse] = await Promise.all([
    backendFetchWithAuth(`/projects/${projectId}`),
    backendFetchWithAuth(`/projects/${projectId}/videos`),
  ]);
  if (projectResponse.status === 404) notFound();
  const project = (await projectResponse.json()) as Project;
  const videos = videosResponse.ok ? (await videosResponse.json()) as Video[] : [];

  return (
    <main className="mx-auto min-h-screen max-w-5xl p-6">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <p className="text-sm text-slate-600"><Link href="/projects" className="hover:underline">Projects</Link></p>
          <h1 className="mt-1 text-3xl font-semibold">{project.name}</h1>
          {project.description && <p className="mt-1 text-sm text-slate-600">{project.description}</p>}
        </div>
        <div className="flex gap-3">
          <Button variant="outline" asChild><Link href="/projects">All projects</Link></Button>
          <LogoutButton />
        </div>
      </header>
      <section className="mt-8">
        <h2 className="text-xl font-semibold">Videos in this project</h2>
        {videos.length === 0 ? (
          <div className="mt-4">
            <EmptyState>No videos in this project yet. Assign videos from the dashboard, or pick this project when uploading.</EmptyState>
          </div>
        ) : (
          <ul className="mt-4 space-y-3">
            {videos.map((video) => (
              <li key={video.id} className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div>
                  <p className="font-medium text-slate-900">{video.filename}</p>
                  <p className="text-sm text-slate-500">{formatFileSize(video.size_bytes)} · {video.status}</p>
                </div>
                <Button variant="outline" size="sm" asChild><a href={`/videos/${video.id}/subtitles`}>Open</a></Button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
