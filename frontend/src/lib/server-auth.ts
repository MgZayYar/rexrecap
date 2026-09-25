import { cookies } from "next/headers";

import { AUTH_COOKIE, type AuthUser } from "@/lib/auth";
import { backendFetch } from "@/lib/backend";

export async function getServerSession(): Promise<{ token: string; user: AuthUser } | null> {
  const token = (await cookies()).get(AUTH_COOKIE)?.value;
  if (!token) return null;

  const response = await backendFetch("/auth/me", { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) return null;
  return { token, user: (await response.json()) as AuthUser };
}
