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
  /** Caminho relativo à base da API (que já inclui `/api/v1`), ex.: "/health". */
  path: string;
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  /**
   * Corpo binario (ex.: upload de avatar). Quando presente, tem prioridade
   * sobre `body` e nao e serializado como JSON.
   */
  rawBody?: BodyInit;
  /** Content-Type do `rawBody` (ex.: "image/png"). */
  contentType?: string;
  headers?: Record<string, string>;
  /** Timeout em milissegundos. */
  timeoutMs?: number;
  /** Locale para enviar no header Accept-Language (ex.: "pt-BR", "en", "es", "ar"). */
  locale?: string;
  /**
   * Signal opcional para cancelamento cooperativo (ex.: signal do React Query).
   * Quando abortado, o chamador recebe o `AbortError` original (não `ApiError`).
   */
  signal?: AbortSignal;
}

export interface HttpResponse<T> {
  status: number;
  headers: Readonly<Record<string, string>>;
  body: T;
}

export interface HttpClient {
  request<T>(request: HttpRequest): Promise<HttpResponse<T>>;
}
