import { redirect } from "next/navigation";

import { LogoutButton } from "@/components/logout-button";
import {
  NotificationCreateForm,
  NotificationSettingRow,
  type NotificationSetting,
} from "@/components/notification-settings";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/feedback";
import { backendFetchWithAuth } from "@/lib/server-backend";
import { getServerSession } from "@/lib/server-auth";

export default async function NotificationsPage() {
  const session = await getServerSession();
  if (!session) redirect("/login");
  const response = await backendFetchWithAuth("/notifications/settings");
  const settings = response.ok ? ((await response.json()) as NotificationSetting[]) : [];

  return (
    <main className="mx-auto min-h-screen max-w-5xl p-6">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <p className="text-sm text-slate-600">Signed in as {session.user.email}</p>
          <h1 className="mt-1 text-3xl font-semibold">Notifications</h1>
          <p className="mt-1 text-sm text-slate-600">
            Get an email or a webhook ping when a processing job finishes.
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" asChild>
            <a href="/dashboard">Dashboard</a>
          </Button>
          <LogoutButton />
        </div>
      </header>
      <section className="mt-8 grid gap-8 md:grid-cols-[320px_1fr]">
        <NotificationCreateForm />
        <div>
          {settings.length === 0 ? (
            <EmptyState>No alerts yet. Add an email address or a webhook URL to get notified.</EmptyState>
          ) : (
            <ul className="space-y-3">
              {settings.map((setting) => (
                <NotificationSettingRow key={setting.id} setting={setting} />
              ))}
            </ul>
          )}
          <p className="mt-4 text-sm text-slate-500">
            Email delivery needs the SMTP_* settings in the backend environment. Webhook pings
            POST a JSON payload with an X-RexCrop-Event header.
          </p>
        </div>
      </section>
    </main>
  );
}
