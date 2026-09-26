"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { apiDelete, apiPatch, apiPost, toMessage } from "@/lib/api-client";

export interface NotificationSetting {
  id: number;
  channel: "email" | "webhook";
  target: string;
  events: string[];
  enabled: boolean;
}

const EVENT_LABELS: Record<string, string> = {
  job_completed: "Completed",
  job_failed: "Failed",
  job_cancelled: "Cancelled",
};

const ALL_EVENTS = ["job_completed", "job_failed", "job_cancelled"];

export function NotificationCreateForm() {
  const router = useRouter();
  const [channel, setChannel] = useState<"email" | "webhook">("email");
  const [target, setTarget] = useState("");
  const [events, setEvents] = useState<string[]>(["job_completed", "job_failed"]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleEvent(event: string) {
    setEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]
    );
  }

  async function submit(formEvent: React.FormEvent) {
    formEvent.preventDefault();
    if (target.trim() === "" || saving || events.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      await apiPost<NotificationSetting>("/api/notifications/settings", {
        channel,
        target: target.trim(),
        events,
      });
      setTarget("");
      router.refresh();
    } catch (err) {
      setError(toMessage(err, "Could not save the notification setting."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={(event) => void submit(event)}
      className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
    >
      <h2 className="font-medium">New alert</h2>
      <div className="mt-3 grid gap-3">
        <select
          aria-label="Channel"
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          value={channel}
          onChange={(event) => setChannel(event.target.value as "email" | "webhook")}
        >
          <option value="email">Email</option>
          <option value="webhook">Webhook</option>
        </select>
        <input
          aria-label={channel === "email" ? "Email address" : "Webhook URL"}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          placeholder={channel === "email" ? "you@example.com" : "https://example.com/hook"}
          value={target}
          onChange={(event) => setTarget(event.target.value)}
          maxLength={512}
        />
        <fieldset>
          <legend className="text-sm font-medium text-slate-700">Notify me when a job is</legend>
          <div className="mt-2 flex flex-wrap gap-3">
            {ALL_EVENTS.map((event) => (
              <label key={event} className="flex items-center gap-1.5 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={events.includes(event)}
                  onChange={() => toggleEvent(event)}
                />
                {EVENT_LABELS[event]}
              </label>
            ))}
          </div>
        </fieldset>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <Button type="submit" disabled={saving || target.trim() === "" || events.length === 0}>
          {saving ? "Saving…" : "Add alert"}
        </Button>
      </div>
    </form>
  );
}

export function NotificationSettingRow({ setting }: { setting: NotificationSetting }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tested, setTested] = useState(false);

  async function run<T>(fn: () => Promise<T>, onOk?: () => void) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await fn();
      onOk?.();
      router.refresh();
    } catch (err) {
      setError(toMessage(err, "That did not work."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="min-w-0">
        <p className="font-medium text-slate-900">
          <span className="mr-2 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
            {setting.channel}
          </span>
          <span className="break-all text-sm">{setting.target}</span>
        </p>
        <p className="mt-1 text-sm text-slate-600">
          {setting.events.map((e) => EVENT_LABELS[e] ?? e).join(", ")}
          {!setting.enabled && " · paused"}
        </p>
        {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
        {tested && !error && <p className="mt-1 text-sm text-green-700">Test sent.</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={busy}
          onClick={() =>
            void run(
              () =>
                apiPatch<NotificationSetting>(`/api/notifications/settings/${setting.id}`, {
                  enabled: !setting.enabled,
                })
            )
          }
        >
          {setting.enabled ? "Pause" : "Resume"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={busy}
          onClick={() =>
            void run(() => apiPost(`/api/notifications/settings/${setting.id}/test`), () =>
              setTested(true)
            )
          }
        >
          Send test
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={busy}
          onClick={() => void run(() => apiDelete(`/api/notifications/settings/${setting.id}`))}
        >
          Delete
        </Button>
      </div>
    </li>
  );
}
