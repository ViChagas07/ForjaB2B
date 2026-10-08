import type { AuthSession } from "@/core/domain/auth";

import { authApi, problemCode } from "@/infrastructure/http";

import { useAuthStore } from "./auth-store";

/**
 * Orquestração de autenticação (cross-cutting, compartilhada entre features).
 *
 * Centraliza login/refresh/logout para evitar duplicar chamadas de API e
 * tratamento de erro. Cada função chama o adapter HTTP e atualiza a store
 * (fonte de verdade) + persistência local.
 */

export async function login(email: string, password: string): Promise<AuthSession> {
  const session = await authApi.login(email, password);
  useAuthStore.getState().setSession(session);
  return session;
}

export async function logout(): Promise<void> {
  const session = useAuthStore.getState().session;
  if (session) {
    try {
      await authApi.logout(session.refresh_token);
    } catch {
      // Best-effort: a revogação no servidor pode falhar; a sessão local é
      // limpa mesmo assim (o refresh token local não será reutilizado).
    }
  }
  useAuthStore.getState().clearSession();
}

/**
 * Rotaciona o refresh token e devolve a sessão atualizada (merge de tokens +
 * perfil existente). Lança `ApiError` quando o refresh é rejeitado
 * (`invalid_refresh_token`), momento em que a UI deve redirecionar ao login.
 */
export async function refreshSession(): Promise<AuthSession> {
  const session = useAuthStore.getState().session;
  if (!session) {
    throw new Error("No active session");
  }
  try {
    const tokens = await authApi.refresh(session.refresh_token);
    const next: AuthSession = { ...session, ...tokens };
    useAuthStore.getState().setSession(next);
    return next;
  } catch (error) {
    // Refresh rejeitado (revogado/rotacionado): a sessão não é mais válida,
    // então limpa o estado local para forçar re-login.
    if (problemCode(error) === "invalid_refresh_token") {
      useAuthStore.getState().clearSession();
    }
    throw error;
  }
}

/** Access token atual (sem disparar re-render); usado em chamadas autenticadas. */
export function getAccessToken(): string | null {
  return useAuthStore.getState().session?.access_token ?? null;
}
