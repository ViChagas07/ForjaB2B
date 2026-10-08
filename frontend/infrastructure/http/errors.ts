import { z } from "zod";

import { DomainError } from "@/core/domain/errors";

/**
 * application/problem+json — contrato RFC 7807 do backend Forja B2B.
 *
 * O backend responde erros no formato único abaixo:
 *   { type, title, status, detail?, instance?, trace_id? }
 * onde `type` é estável (urn:forja:problem:{code}) e `trace_id` permite
 * correlacionar com logs/traces. A validação é feita com Zod para garantir
 * robustez na fronteira HTTP.
 */

export const PROBLEM_JSON_MEDIA_TYPE = "application/problem+json";

export const problemDetailsSchema = z.object({
  type: z.string(),
  title: z.string(),
  status: z.number().int(),
  detail: z.string().optional(),
  instance: z.string().optional(),
  trace_id: z.string().optional(),
});

export type ProblemDetails = z.infer<typeof problemDetailsSchema>;

export function isProblemDetails(value: unknown): value is ProblemDetails {
  return problemDetailsSchema.safeParse(value).success;
}

/**
 * Erro tipado derivado de um Problem Details. `code` herda de `type`, o que
 * mantém o identificador estável do backend acessível ao frontend.
 */
export class ApiError extends DomainError {
  readonly status: number;
  readonly type: string;
  readonly title: string;
  readonly instance?: string;
  readonly traceId?: string;

  constructor(problem: ProblemDetails) {
    super(problem.type, problem.detail ?? problem.title, problem.detail);
    this.status = problem.status;
    this.type = problem.type;
    this.title = problem.title;
    this.instance = problem.instance;
    this.traceId = problem.trace_id;
  }
}

/** Converte um ProblemDetails (RFC 7807) em um `ApiError` tipado. */
export function toApiError(problem: ProblemDetails): ApiError {
  return new ApiError(problem);
}

const PROBLEM_TYPE_PREFIX = "urn:forja:problem:";

/**
 * Extrai o código estável de erro (sufixo de `type`), ex.: `invalid_credentials`.
 *
 * Usado na UI para mapear erros RFC 7807 para mensagens amigáveis. Devolve
 * `null` quando o valor não é um `ApiError` (ex.: erro de rede não tipado).
 */
export function problemCode(error: unknown): string | null {
  if (!(error instanceof ApiError)) {
    return null;
  }
  return error.type.startsWith(PROBLEM_TYPE_PREFIX)
    ? error.type.slice(PROBLEM_TYPE_PREFIX.length)
    : error.type;
}
