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

/** Tipo da conta: pessoa física (CPF) x empresa (CNPJ). */
export const ACCOUNT_TYPES = ["PERSON", "COMPANY"] as const;

export type AccountType = (typeof ACCOUNT_TYPES)[number];

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  account_type: AccountType;
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
 * - `registration_required`: o e-mail verificado pelo Google ainda não possui
 *   conta; o frontend redireciona para o cadastro CPF com os dados
 *   pré-preenchidos. Nenhuma conta é criada automaticamente.
 *
 * Nenhum token/secret trafega na URL de redirect; apenas o exchange code opaco.
 */
export type OAuthExchangeResult =
  | { status: "authenticated"; session: AuthSession }
  | { status: "registration_required"; email: string | null; full_name: string | null };
