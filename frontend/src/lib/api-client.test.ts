import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiGet, apiPost, toMessage } from "@/lib/api-client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api-client", () => {
  it("resolves parsed JSON on success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ id: 1 })));
    await expect(apiGet<{ id: number }>("/api/videos")).resolves.toEqual({ id: 1 });
  });

  it("throws ApiError with the backend detail on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "Not authenticated" }, 401)));
    const error = (await apiGet("/api/videos").catch((err) => err)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(401);
    expect(error.detail).toBe("Not authenticated");
  });

  it("falls back to a generic message when the error body is not JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("oops", { status: 500 })));
    const error = (await apiGet("/api/videos").catch((err) => err)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.detail).toBe("Something went wrong. Please try again.");
  });

  it("posts JSON bodies with the right content type", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await apiPost("/api/auth/login", { email: "a@b.c", password: "secret1234" });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(String(init.body))).toEqual({ email: "a@b.c", password: "secret1234" });
  });

  it("toMessage prefers the ApiError detail and otherwise uses the fallback", () => {
    expect(toMessage(new ApiError(404, "Missing"), "fallback")).toBe("Missing");
    expect(toMessage(new Error("boom"), "fallback")).toBe("fallback");
  });
});
