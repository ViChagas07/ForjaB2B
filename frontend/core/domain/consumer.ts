/**
 * Contratos do cadastro de cliente consumidor (conta CPF).
 *
 * Campos em snake_case para refletir exatamente o JSON do backend. O CEP é
 * enviado sem máscara (8 dígitos) e a data de nascimento em ISO (YYYY-MM-DD).
 */

export const GENDERS = [
  "FEMININO",
  "MASCULINO",
  "NAO_BINARIO",
  "OUTRO",
  "PREFIRO_NAO_INFORMAR",
] as const;

export type Gender = (typeof GENDERS)[number];

export interface RegisterConsumerInput {
  full_name: string;
  email: string;
  password: string;
  cpf: string;
  birth_date: string;
  postal_code: string;
  gender: Gender;
  consent: boolean;
}

export interface RegisterConsumerResult {
  company_id: string;
  user_id: string;
}
