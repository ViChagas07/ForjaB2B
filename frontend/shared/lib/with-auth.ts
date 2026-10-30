import { problemCode } from "@/infrastructure/http";
import { refreshSession } from "@/shared/stores/auth-actions";
import { useAuthStore } from "@/shared/stores/auth-store";

/**
 * Refresh single-flight: varias queries autenticadas podem receber 401 ao
 * mesmo tempo (ex.: carrinho + credito). Apenas uma rotaciona o refresh token;
 * as demais aguardam a mesma Promise. Sem isso, a segunda rotacao usa um token
 * ja consumido e derruba a sessao.
 */
let refreshInFlight: Promise<unknown> | null = null;

function refreshOnce(): Promise<unknown> {
  if (!refreshInFlight) {
    refreshInFlight = refreshSession().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

/**
 * Executa uma chamada autenticada com rotacao transparente do access token.
 *
 * Consolida o padrao usado nas features: le o token atual, executa `request`
 * e, caso o backend acuse token expirado/invalido, rotaciona a sessao e repete
 * a chamada uma unica vez com o novo token. Se outra requisicao ja rotacionou,
 * reutiliza a sessao mais nova em vez de limpar o login.
 */
export async function withAuth<T>(request: (accessToken: string) => Promise<T>): Promise<T> {
  const initialToken = useAuthStore.getState().session?.access_token;
  if (!initialToken) {
    throw new Error("unauthenticated");
  }

  try {
    return await request(initialToken);
  } catch (error) {
    const code = problemCode(error);
    if (code === "token_expired" || code === "invalid_token") {
      try {
        await refreshOnce();
      } catch {
        const latest = useAuthStore.getState().session;
        if (latest && latest.access_token !== initialToken) {
          return request(latest.access_token);
        }
        throw error;
      }
      const newToken = useAuthStore.getState().session?.access_token;
      if (newToken) {
        return request(newToken);
      }
    }
    throw error;
  }
}
