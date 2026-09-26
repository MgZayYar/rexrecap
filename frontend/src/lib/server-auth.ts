import { type AuthUser } from "@/lib/auth";
import { backendFetchWithAuth, getAuthToken } from "@/lib/server-backend";

export async function getServerSession(): Promise<{ token: string; user: AuthUser } | null> {
  const token = await getAuthToken();
  if (!token) return null;

  const response = await backendFetchWithAuth("/auth/me");
  if (!response.ok) return null;
  return { token, user: (await response.json()) as AuthUser };
}
