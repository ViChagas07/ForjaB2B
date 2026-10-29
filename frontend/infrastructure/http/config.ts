/**
 * Configuração do cliente HTTP.
 *
 * No navegador a API é sempre same-origin: as chamadas usam `/api/v1` e o
 * rewrite do Next encaminha para o backend. Assim não há preflight CORS e
 * nenhuma URL de backend precisa ir para o bundle.
 *
 * No servidor (Server Components), `BACKEND_URL` é lida diretamente do
 * ambiente do processo e a chamada vai para o backend sem passar pelo rewrite.
 */

const API_PREFIX = "/api/v1";
const DEV_BACKEND_URL = "http://localhost:8000";

export const DEFAULT_API_BASE_URL = `${DEV_BACKEND_URL}${API_PREFIX}`;

function serverBackendUrl(): string {
  const configured = process.env.BACKEND_URL?.trim();
  if (configured) {
    return configured.replace(/\/+$/, "");
  }
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      "BACKEND_URL não definida: configure a variável de servidor no painel da Vercel " +
        "(ex.: https://forjab2b.onrender.com) e faça um novo deploy.",
    );
  }
  return DEV_BACKEND_URL;
}

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return API_PREFIX;
  }
  return `${serverBackendUrl()}${API_PREFIX}`;
}
