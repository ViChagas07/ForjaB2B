import type { HttpClient, HttpRequest, HttpResponse } from "@/core/application/ports/http-client";
import { ApiError, isProblemDetails } from "./errors";

const DEFAULT_TIMEOUT_MS = 15_000;

function buildUrl(baseUrl: string, request: HttpRequest): string {
  const normalizedBase = baseUrl.replace(/\/+$/, "");
  const normalizedPath = request.path.startsWith("/") ? request.path : `/${request.path}`;
  const isAbsolute = /^https?:\/\//i.test(normalizedBase);
  // Em produção no navegador a base é relativa (`/api/v1`); a URL dummy só
  // existe para o parser e nunca é usada na requisição.
  const url = new URL(
    `${normalizedBase}${normalizedPath}`,
    isAbsolute ? undefined : "http://same-origin.local",
  );
  if (request.query) {
    for (const [key, value] of Object.entries(request.query)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return isAbsolute ? url.toString() : `${url.pathname}${url.search}`;
}

/** Gera um request ID (correlation) enviado no header `X-Request-ID`. */
function newRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16);
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function toHeaderRecord(headers: Headers): Record<string, string> {
  const record: Record<string, string> = {};
  headers.forEach((value, key) => {
    record[key] = value;
  });
  return record;
}

function toNetworkError(cause: unknown): ApiError {
  const detail = cause instanceof Error ? cause.message : "Falha de rede ou timeout.";
  return new ApiError({
    type: "urn:forja:problem:network_error",
    title: "Network Error",
    status: 0,
    detail,
  });
}

async function toApiError(response: Response, contentType: string): Promise<ApiError> {
  const text = await response.text();

  if (contentType.includes("application/problem+json")) {
    try {
      const json = JSON.parse(text) as unknown;
      if (isProblemDetails(json)) {
        return new ApiError(json);
      }
    } catch {
      // Resposta problem+json inválida: cai no fallback abaixo.
    }
  }

  return new ApiError({
    type: `urn:forja:problem:http_${response.status}`,
    title: response.statusText || "HTTP Error",
    status: response.status,
    detail: text || undefined,
  });
}

/**
 * Implementação da porta `HttpClient` baseada em fetch.
 *
 * Trata: base URL, headers (incl. correlation `X-Request-ID`, `Accept-Language`), timeout via
 * AbortController, parsing de `application/problem+json` (RFC 7807) e erros
 * tipados (`ApiError`). Nenhum `fetch()` deve ser chamado diretamente em
 * componentes; use esta classe (via `apiClient`).
 */
export class FetchHttpClient implements HttpClient {
  constructor(private readonly baseUrl: string) {}

  async request<T>(request: HttpRequest): Promise<HttpResponse<T>> {
    // Signal já abortado: nenhuma requisição é iniciada (mesmo contrato do fetch).
    if (request.signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }

    const url = buildUrl(this.baseUrl, request);

    const headers: Record<string, string> = {
      Accept: "application/json, application/problem+json",
      "X-Request-ID": newRequestId(),
      ...request.headers,
    };
    if (request.body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    // Adiciona Accept-Language se locale for fornecido
    if (request.locale) {
      headers["Accept-Language"] = request.locale;
    }

    const controller = new AbortController();
    const timeoutMs = request.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    // Cancelamento externo (ex.: signal do React Query): propaga para o
    // controller interno sem interferir no timeout.
    const externalSignal = request.signal;
    const onExternalAbort = (): void => controller.abort();
    if (externalSignal) {
      if (externalSignal.aborted) {
        onExternalAbort();
      } else {
        externalSignal.addEventListener("abort", onExternalAbort, { once: true });
      }
    }

    let response: Response;
    try {
      response = await fetch(url, {
        method: request.method,
        headers,
        body: request.body === undefined ? undefined : JSON.stringify(request.body),
        signal: controller.signal,
        cache: "no-store",
      });
    } catch (cause) {
      // Abort EXTERNO não é falha de rede: repassa o AbortError original para
      // o chamador (React Query trata como cancelamento, não como erro).
      if (externalSignal?.aborted) {
        throw cause;
      }
      throw toNetworkError(cause);
    } finally {
      clearTimeout(timer);
      if (externalSignal) {
        externalSignal.removeEventListener("abort", onExternalAbort);
      }
    }

    return this.parseResponse<T>(response);
  }

  private async parseResponse<T>(response: Response): Promise<HttpResponse<T>> {
    const headers = toHeaderRecord(response.headers);
    const contentType = response.headers.get("content-type") ?? "";

    if (!response.ok) {
      throw await toApiError(response, contentType);
    }

    if (response.status === 204) {
      return { status: response.status, headers, body: undefined as T };
    }

    const text = await response.text();
    let body: T;
    if (text) {
      try {
        body = JSON.parse(text) as T;
      } catch {
        body = text as unknown as T;
      }
    } else {
      body = undefined as T;
    }

    return { status: response.status, headers, body };
  }
}
