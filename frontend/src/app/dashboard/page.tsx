import Link from "next/link";
import { redirect } from "next/navigation";

import { LogoutButton } from "@/components/logout-button";
import { JobStatus } from "@/components/job-status";
import { VideoJobActions } from "@/components/video-job-actions";
import { VideoProjectAssign } from "@/components/video-project-assign";
import { WorkerStatus } from "@/components/worker-status";
import { Button } from "@/components/ui/button";
import { backendFetchWithAuth } from "@/lib/server-backend";
import { getServerSession } from "@/lib/server-auth";
import { formatFileSize, type Video } from "@/lib/video";

export default async function DashboardPage() {
  const session = await getServerSession();
  if (!session) redirect("/login");
  const videosResponse = await backendFetchWithAuth("/videos");
  const videos = videosResponse.ok ? (await videosResponse.json()) as Video[] : [];

  return (
    <main className="mx-auto min-h-screen max-w-5xl p-6">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5"><div><p className="text-sm text-slate-600">Signed in as {session.user.email}</p><h1 className="mt-1 text-3xl font-semibold">Dashboard</h1><div className="mt-2"><WorkerStatus /></div></div><div className="flex gap-3"><Button variant="outline" asChild><Link href="/projects">Projects</Link></Button><Button variant="outline" asChild><Link href="/settings/notifications">Notifications</Link></Button><Button asChild><a href="/upload">Upload video</a></Button><LogoutButton /></div></header>
      <section className="mt-8"><div className="mb-4"><h2 className="text-xl font-semibold">Uploaded videos</h2><p className="mt-1 text-sm text-slate-600">Start a workflow or follow its processing state below.</p></div>{videos.length === 0 ? <div className="rounded-lg border border-dashed border-slate-300 p-8 text-slate-600">No videos uploaded yet. Upload your first video to get started.</div> : <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="w-full min-w-[980px] text-left text-sm"><thead className="bg-slate-50 text-slate-600"><tr><th className="px-4 py-3 font-medium">Filename</th><th className="px-4 py-3 font-medium">Project</th><th className="px-4 py-3 font-medium">Uploaded</th><th className="px-4 py-3 font-medium">Upload status</th><th className="px-4 py-3 font-medium">Processing</th><th className="px-4 py-3 font-medium text-right">Workflows</th><th className="px-4 py-3 font-medium text-right">Action</th></tr></thead><tbody>{videos.map((video) => <tr key={video.id} className="border-t border-slate-200"><td className="px-4 py-3"><p className="font-medium text-slate-900">{video.filename}</p><p className="text-slate-500">{formatFileSize(video.size_bytes)}</p></td><td className="px-4 py-3"><VideoProjectAssign video={video} /></td><td className="px-4 py-3 text-slate-600">{new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(video.created_at))}</td><td className="px-4 py-3"><span className="rounded-full bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700">{video.status}</span></td><td className="px-4 py-3"><JobStatus videoId={video.id} /></td><td className="px-4 py-3"><VideoJobActions videoId={video.id} /></td><td className="px-4 py-3 text-right"><div className="flex justify-end gap-2"><Button variant="outline" size="sm" asChild><a href={`/videos/${video.id}/subtitles`}>Edit subtitles</a></Button><Button variant="outline" size="sm" asChild><a href={`/videos/${video.id}/transcript`}>Transcript</a></Button><Button variant="outline" size="sm" asChild><a href={`/videos/${video.id}/dubbing`}>Dubbing</a></Button><Button variant="outline" size="sm" asChild><a href={`/videos/${video.id}/shorts`}>Shorts</a></Button><Button variant="outline" size="sm" asChild><a href={`/videos/${video.id}/thumbnails`}>Thumbnails</a></Button><Button variant="outline" size="sm" asChild><a href={`/api/videos/${video.id}/download`}>Download</a></Button></div></td></tr>)}</tbody></table></div>}</section>
    </main>
  );
}
