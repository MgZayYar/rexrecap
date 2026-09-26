import Link from "next/link";
import { redirect } from "next/navigation";

import { LogoutButton } from "@/components/logout-button";
import { DashboardVideos } from "@/components/dashboard-videos";
import { WorkerStatus } from "@/components/worker-status";
import { Button } from "@/components/ui/button";
import { backendFetchWithAuth } from "@/lib/server-backend";
import { getServerSession } from "@/lib/server-auth";
import { type Video } from "@/lib/video";

export default async function DashboardPage() {
  const session = await getServerSession();
  if (!session) redirect("/login");
  const videosResponse = await backendFetchWithAuth("/videos");
  const videos = videosResponse.ok ? (await videosResponse.json()) as Video[] : [];

  return (
    <main className="mx-auto min-h-screen max-w-5xl p-6">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5"><div><p className="text-sm text-slate-600">Signed in as {session.user.email}</p><h1 className="mt-1 text-3xl font-semibold">Dashboard</h1><div className="mt-2"><WorkerStatus /></div></div><div className="flex gap-3"><Button variant="outline" asChild><Link href="/projects">Projects</Link></Button><Button variant="outline" asChild><Link href="/settings/notifications">Notifications</Link></Button><Button variant="outline" asChild><Link href="/batch">Batch</Link></Button><Button asChild><a href="/upload">Upload video</a></Button><LogoutButton /></div></header>
      <section className="mt-8"><div className="mb-4"><h2 className="text-xl font-semibold">Uploaded videos</h2><p className="mt-1 text-sm text-slate-600">Start a workflow or follow its processing state below.</p></div><DashboardVideos videos={videos} /></section>
    </main>
  );
}
