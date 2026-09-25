"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type AuthFormProps = { mode: "login" | "register" };

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isRegister = mode === "register";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");

    if (!EMAIL_PATTERN.test(email)) return setError("Enter a valid email address.");
    if (password.length < 8) return setError("Password must contain at least 8 characters.");

    setError(null);
    setIsSubmitting(true);
    const response = await fetch(`/api/auth/${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    setIsSubmitting(false);

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      setError(body?.detail ?? "Unable to continue. Please try again.");
      return;
    }
    router.replace("/dashboard");
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <div><label className="mb-1.5 block text-sm font-medium" htmlFor="email">Email</label><Input id="email" name="email" type="email" autoComplete="email" required /></div>
      <div><label className="mb-1.5 block text-sm font-medium" htmlFor="password">Password</label><Input id="password" name="password" type="password" autoComplete={isRegister ? "new-password" : "current-password"} minLength={8} required /></div>
      {error && <p className="text-sm text-red-600" role="alert">{error}</p>}
      <Button className="w-full" type="submit" disabled={isSubmitting}>{isSubmitting ? "Please wait…" : isRegister ? "Create account" : "Sign in"}</Button>
      <p className="text-center text-sm text-slate-600">{isRegister ? "Already have an account?" : "Need an account?"} <Link className="font-medium text-slate-900 underline" href={isRegister ? "/login" : "/register"}>{isRegister ? "Sign in" : "Register"}</Link></p>
    </form>
  );
}
