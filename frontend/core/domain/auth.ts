/**
 * Contratos de autenticação (neutros, sem frameworks).
 *
 * Os nomes de campos refletem exatamente o JSON devolvido pelo backend
 * (snake_case), evitando uma camada extra de mapeamento e divergência de
 * contrato. `AuthSession` é a sessão completa após login (par de tokens +
 * perfil mínimo); `AuthTokens` é o resultado da rotação de refresh (sem
 * perfil: o backend não reconsulta o usuário).
 */

export const ROLES = ["ADMIN", "BUYER", "APPROVER", "FINANCE"] as const;

export type Role = (typeof ROLES)[number];

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: Role;
}

export interface AuthSession {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/**
 * Resultado da troca do exchange code OAuth (`POST /api/v1/auth/oauth/exchange`).
 *
 * - `authenticated`: sessão completa (mesma forma de `AuthSession`).
 * - `onboarding`: usuário ainda não existe; o frontend redireciona para o
 *   onboarding pré-preenchendo email/nome vindos do Google.
 *
 * Nenhum token/secret trafega na URL de redirect; apenas o exchange code opaco.
 */
export type OAuthExchangeResult =
  | { status: "authenticated"; session: AuthSession }
  | { status: "onboarding"; email: string | null; full_name: string | null };
