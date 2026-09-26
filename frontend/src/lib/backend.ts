export const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000/api/v1";

export async function readError(response: Response): Promise<string> {
  const body = await response.json().catch(() => null);
  return body?.detail ?? "Something went wrong. Please try again.";
}
