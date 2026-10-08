import { afterEach, describe, expect, it, vi } from "vitest";

import { FetchHttpClient } from "@/infrastructure/http/api-client";
import { ApiError, isProblemDetails } from "@/infrastructure/http/errors";

function jsonResponse(body: unknown, init?: { status?: number; contentType?: string }): Response {
  return new Response(JSON.stringify(body), {
    status: init?.status ?? 200,
    headers: { "content-type": init?.contentType ?? "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("isProblemDetails (RFC 7807)", () => {
  it("aceita um Problem Details válido", () => {
    expect(isProblemDetails({ type: "urn:forja:problem:x", title: "X", status: 400 })).toBe(true);
  });

  it("rejeita valores inválidos", () => {
    expect(isProblemDetails(null)).toBe(false);
    expect(isProblemDetails("not-an-object")).toBe(false);
    expect(isProblemDetails({ type: "t" })).toBe(false);
    expect(isProblemDetails({ title: "t", status: 400 })).toBe(false);
  });
});

describe("ApiError", () => {
  it("mapeia todos os campos do Problem Details", () => {
    const error = new ApiError({
      type: "urn:forja:problem:not_found",
      title: "Not Found",
      status: 404,
      detail: "Recurso ausente",
      instance: "/api/v1/x",
      trace_id: "abc123",
    });

    expect(error.code).toBe("urn:forja:problem:not_found");
    expect(error.status).toBe(404);
    expect(error.title).toBe("Not Found");
    expect(error.detail).toBe("Recurso ausente");
    expect(error.instance).toBe("/api/v1/x");
    expect(error.traceId).toBe("abc123");
  });
});

describe("FetchHttpClient", () => {
  const baseUrl = "http://localhost:8000";

  it("parseia resposta JSON de sucesso", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ id: 1 })));

    const client = new FetchHttpClient(baseUrl);
    const res = await client.request<{ id: number }>({ method: "GET", path: "/api/v1/foo" });

    expect(res.status).toBe(200);
    expect(res.body).toEqual({ id: 1 });
  });

  it("lança ApiError tipado para application/problem+json", async () => {
    const problem = {
      type: "urn:forja:problem:not_found",
      title: "Not Found",
      status: 404,
      detail: "Recurso ausente",
      trace_id: "trace-1",
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(problem, { status: 404, contentType: "application/problem+json" }),
        ),
    );

    const client = new FetchHttpClient(baseUrl);
    await expect(client.request({ method: "GET", path: "/api/v1/missing" })).rejects.toMatchObject({
      status: 404,
      type: "urn:forja:problem:not_found",
      traceId: "trace-1",
    });
  });

  it("lança ApiError de rede quando o fetch falha", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    const client = new FetchHttpClient(baseUrl);
    await expect(client.request({ method: "GET", path: "/api/v1/foo" })).rejects.toMatchObject({
      status: 0,
      type: "urn:forja:problem:network_error",
    });
  });

  it("envia correlation id e content-type nos headers", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const client = new FetchHttpClient(baseUrl);
    await client.request({ method: "POST", path: "/api/v1/foo", body: { a: 1 } });

    const [, init] = fetchMock.mock.calls[0] ?? [null, {}];
    const headers = (init?.headers ?? {}) as Record<string, string>;

    expect(headers["X-Request-ID"]).toBeTruthy();
    expect(headers["Content-Type"]).toBe("application/json");
  });
});
