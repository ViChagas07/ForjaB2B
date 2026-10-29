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

  it("monta URL relativa no navegador (base same-origin)", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const client = new FetchHttpClient("/api/v1");
    await client.request({
      method: "GET",
      path: "/catalog/products",
      query: { page_size: 50 },
    });

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe("/api/v1/catalog/products?page_size=50");
  });

  it("monta URL absoluta no servidor (BACKEND_URL)", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const client = new FetchHttpClient("https://forjab2b.onrender.com/api/v1");
    await client.request({
      method: "GET",
      path: "/catalog/products",
      query: { page_size: 50 },
    });

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      "https://forjab2b.onrender.com/api/v1/catalog/products?page_size=50",
    );
  });

  it("repassa o cancelamento externo como AbortError (não ApiError de rede)", async () => {
    // Simula o fetch real: rejeita com AbortError quando o signal interno aborta.
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(
      (_url, init) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true },
          );
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = new FetchHttpClient(baseUrl);
    const external = new AbortController();
    const pending = client.request({
      method: "GET",
      path: "/api/v1/foo",
      signal: external.signal,
    });
    external.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });

  it("rejeita imediatamente quando o signal externo já está abortado", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const client = new FetchHttpClient(baseUrl);
    const external = new AbortController();
    external.abort();

    await expect(
      client.request({ method: "GET", path: "/api/v1/foo", signal: external.signal }),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
