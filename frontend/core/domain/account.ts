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
  account_type: "PERSON" | "COMPANY";
  role: string;
}

export interface AccountPreferences {
  display_currency: CurrencyCode;
}

export interface UpdateAccountInput {
  full_name: string;
  phone: string | null;
  birth_date: string | null;
  gender: Gender | null;
  postal_code: string | null;
}
