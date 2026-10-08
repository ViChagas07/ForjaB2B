/**
 * Configuração do cliente HTTP.
 *
 * `NEXT_PUBLIC_API_URL` é a única variável de ambiente consumida pelo bundle
 * do browser. Ela é intencionalmente PÚBLICA (prefixo NEXT_PUBLIC_): nenhum
 * segredo (DATABASE_URL, senhas, API secrets, chaves privadas) pode viver aqui.
 */

export const DEFAULT_API_BASE_URL = "http://localhost:8000";

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_BASE_URL;
}
