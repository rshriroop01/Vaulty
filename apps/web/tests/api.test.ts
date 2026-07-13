import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError } from "@/lib/api";

afterEach(() => vi.restoreAllMocks());

describe("apiFetch", () => {
  it("returns parsed JSON on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 })),
    );
    await expect(apiFetch("/healthz")).resolves.toEqual({ status: "ok" });
  });

  it("throws ApiError with problem+json fields on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ title: "Not Found", detail: "Document not found", status: 404 }),
            { status: 404 },
          ),
        ),
    );
    const err = await apiFetch("/api/v1/nope").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(404);
    expect((err as ApiError).title).toBe("Not Found");
  });
});
