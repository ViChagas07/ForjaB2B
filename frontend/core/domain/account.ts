/**
 * Perfil da propria conta. Datas usam ISO `YYYY-MM-DD`; o e-mail e somente
 * leitura (nao ha troca de e-mail neste fluxo).
 */

import type { CurrencyCode } from "./currency";

export const GENDERS = [
  "FEMININO",
  "MASCULINO",
  "NAO_BINARIO",
  "OUTRO",
  "PREFIRO_NAO_INFORMAR",
] as const;

export type Gender = (typeof GENDERS)[number];

export interface AccountProfile {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  birth_date: string | null;
  gender: Gender | null;
  postal_code: string | null;
  display_currency: CurrencyCode;
  avatar_url: string | null;
  account_type: "PERSON" | "COMPANY";
  role: string;
  hide_spending: boolean;
}

export interface AccountPreferences {
  display_currency: CurrencyCode;
  hide_spending: boolean;
}

export interface AccountAvatar {
  avatar_url: string | null;
  updated_at: string | null;
}

export interface UpdateAccountInput {
  full_name: string;
  phone: string | null;
  birth_date: string | null;
  gender: Gender | null;
  postal_code: string | null;
}
