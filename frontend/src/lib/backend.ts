export const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000/api";

export async function backendFetch(path: string, init?: RequestInit) {
  return fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });
}

export async function readError(response: Response): Promise<string> {
  const body = await response.json().catch(() => null);
  return body?.detail ?? "Something went wrong. Please try again.";
}
