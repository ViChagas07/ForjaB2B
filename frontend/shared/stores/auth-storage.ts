import type { AuthSession } from "@/core/domain/auth";

/**
 * Persistência da sessão no localStorage.
 *
 * Os tokens são opacos e validados pelo backend (assinatura JWT + store de
 * refresh); aqui apenas guardamos a sessão entre recarregamentos. A leitura é
 * defensiva (corrupção no storage não quebra a aplicação) e todos os acessos
 * são guardados para SSR/ambiente sem `window`.
 */

const STORAGE_KEY = "forja-auth-session";

function isAuthSession(value: unknown): value is AuthSession {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const record = value as Record<string, unknown>;
  const user = record.user as Record<string, unknown> | undefined;
  return (
    typeof record.access_token === "string" &&
    typeof record.refresh_token === "string" &&
    typeof record.token_type === "string" &&
    typeof record.expires_in === "number" &&
    typeof user === "object" &&
    user !== null &&
    typeof user.id === "string" &&
    typeof user.email === "string" &&
    typeof user.full_name === "string" &&
    typeof user.role === "string"
  );
}

export function loadStoredSession(): AuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as unknown;
    return isAuthSession(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function saveStoredSession(session: AuthSession): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Storage indisponível (quota/privacidade): a sessão continua em memória.
  }
}

export function clearStoredSession(): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignora falha de remoção; a sessão em memória já foi limpa.
  }
}
