/**
 * Politica de Seguranca de Conteudo (CSP) do frontend.
 *
 * A politica e montada por requisicao porque o nonce muda a cada resposta.
 * Scripts usam nonce + strict-dynamic (sem `unsafe-inline`); o Next.js le o
 * cabecalho CSP da requisicao e aplica o nonce aos seus proprios scripts.
 * `connect-src`/`img-src` ficam restritos a `'self'`: a API e os assets do
 * backend sao same-origin pelos rewrites do Next. `apiUrl` existe apenas para
 * cenarios controlados (ex.: desenvolvimento com chamada direta).
 */

export interface CspOptions {
  nonce: string;
  apiUrl?: string | null;
  isProduction: boolean;
  isSecure?: boolean;
}

function apiOrigin(apiUrl: string | null | undefined): string {
  if (!apiUrl) {
    return "";
  }
  try {
    return new URL(apiUrl).origin;
  } catch {
    return "";
  }
}

export function buildContentSecurityPolicy({
  nonce,
  apiUrl,
  isProduction,
  isSecure = false,
}: CspOptions): string {
  const api = apiOrigin(apiUrl);
  const connectSources = ["'self'", api].filter(Boolean);
  const imageSources = ["'self'", "data:", "blob:", api].filter(Boolean);
  const scriptSources = [`'nonce-${nonce}'`, "'strict-dynamic'"];
  if (!isProduction) {
    // Next dev compila com eval e usa WebSocket para HMR. Nao vale em producao.
    scriptSources.push("'unsafe-eval'");
    connectSources.push("ws:", "wss:");
  }

  return [
    "default-src 'self'",
    `script-src ${scriptSources.join(" ")}`,
    "style-src 'self' 'unsafe-inline'",
    `img-src ${imageSources.join(" ")}`,
    "font-src 'self' data:",
    `connect-src ${connectSources.join(" ")}`,
    "media-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "manifest-src 'self'",
    "worker-src 'self' blob:",
    ...(isProduction && isSecure ? ["upgrade-insecure-requests"] : []),
  ].join("; ");
}

export function generateNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}
