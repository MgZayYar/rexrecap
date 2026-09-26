"use client";

import type { ReactNode } from "react";

/** Shared loading / empty / error surfaces so every page speaks the same
 *  visual language instead of inventing its own ad-hoc states. */

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-8 text-slate-600" role="status">
      <span
        className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-700"
        aria-hidden="true"
      />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-600">
      {children}
    </div>
  );
}

export function ErrorMessage({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
      {children}
    </p>
  );
}
