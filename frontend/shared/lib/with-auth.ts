import { problemCode } from "@/infrastructure/http";
import { refreshSession } from "@/shared/stores/auth-actions";
import { useAuthStore } from "@/shared/stores/auth-store";

/**
 * Executa uma chamada autenticada com rotação transparente do access token.
 *
 * Consolida o padrão usado nasfeatures: lê o token atual, executa `request` e,
 * caso o backend acuse token expirado/inválido, rotaciona a sessão e repete a
 * chamada uma única vez com o novo token. Se o refresh falhar, a sessão já foi
 * limpa e o erro original propaga para a UI (guard redireciona ao login).
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
      await refreshSession();
      const newToken = useAuthStore.getState().session?.access_token;
      if (newToken) {
        return request(newToken);
      }
    }
    throw error;
  }
}
