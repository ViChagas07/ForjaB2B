/**
 * Porta HTTP — contrato que a camada de aplicação usa para falar com a API.
 *
 * A implementação concreta (fetch) vive em infrastructure/http e implementa
 * esta porta (inversão de dependência). A porta é neutra: não referencia
 * React, Next.js, fetch, Headers/Response do DOM nem browser APIs.
 */

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface HttpRequest {
  method: HttpMethod;
  /** Caminho relativo à base da API, ex.: "/api/v1/health". */
  path: string;
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  headers?: Record<string, string>;
  /** Timeout em milissegundos. */
  timeoutMs?: number;
}

export interface HttpResponse<T> {
  status: number;
  headers: Readonly<Record<string, string>>;
  body: T;
}

export interface HttpClient {
  request<T>(request: HttpRequest): Promise<HttpResponse<T>>;
}
