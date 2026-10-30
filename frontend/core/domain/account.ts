/**
 * Perfil da propria conta. Datas usam ISO `YYYY-MM-DD`; o e-mail e somente
 * leitura (nao ha troca de e-mail neste fluxo).
 */

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
  account_type: "PERSON" | "COMPANY";
  role: string;
}

export interface UpdateAccountInput {
  full_name: string;
  phone: string | null;
  birth_date: string | null;
  gender: Gender | null;
  postal_code: string | null;
}
