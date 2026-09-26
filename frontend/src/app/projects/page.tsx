import Link from "next/link";
import { redirect } from "next/navigation";

import { LogoutButton } from "@/components/logout-button";
import { ProjectCreateForm } from "@/components/project-create-form";
import { ProjectDeleteButton } from "@/components/project-delete-button";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/feedback";
import { backendFetchWithAuth } from "@/lib/server-backend";
import { getServerSession } from "@/lib/server-auth";
import type { Project } from "@/lib/video";

export default async function ProjectsPage() {
  const session = await getServerSession();
  if (!session) redirect("/login");
  const response = await backendFetchWithAuth("/projects");
  const projects = response.ok ? (await response.json()) as Project[] : [];

  return (
    <main className="mx-auto min-h-screen max-w-5xl p-6">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <p className="text-sm text-slate-600">Signed in as {session.user.email}</p>
          <h1 className="mt-1 text-3xl font-semibold">Projects</h1>
          <p className="mt-1 text-sm text-slate-600">Group your videos so each recap has a home.</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" asChild><a href="/dashboard">Dashboard</a></Button>
          <LogoutButton />
        </div>
      </header>
      <section className="mt-8 grid gap-8 md:grid-cols-[320px_1fr]">
        <ProjectCreateForm />
        <div>
          {projects.length === 0 ? (
            <EmptyState>No projects yet. Create one to start grouping videos.</EmptyState>
          ) : (
            <ul className="space-y-3">
              {projects.map((project) => (
                <li key={project.id} className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                  <div>
                    <Link href={`/projects/${project.id}`} className="font-medium text-slate-900 hover:underline">
                      {project.name}
                    </Link>
                    {project.description && <p className="mt-1 text-sm text-slate-600">{project.description}</p>}
                  </div>
                  <ProjectDeleteButton projectId={project.id} projectName={project.name} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}
