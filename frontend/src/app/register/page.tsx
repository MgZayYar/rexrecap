import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/auth-form";
import { AUTH_COOKIE } from "@/lib/auth";

export default async function RegisterPage() {
  if ((await cookies()).has(AUTH_COOKIE)) redirect("/dashboard");

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center p-6">
      <div className="mb-8"><p className="text-sm font-medium text-slate-600">RexCrop</p><h1 className="mt-2 text-3xl font-semibold">Create your account</h1><p className="mt-2 text-slate-600">Start with a secure RexCrop account.</p></div>
      <AuthForm mode="register" />
    </main>
  );
}
