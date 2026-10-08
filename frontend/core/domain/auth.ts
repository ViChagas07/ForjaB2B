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
