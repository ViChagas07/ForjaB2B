import { z } from "zod";

import { isValidCpf } from "@/core/domain";
import { GENDERS } from "@/core/domain/consumer";

const NON_DIGITS = /\D/g;
const MIN_AGE = 18;
const MAX_AGE = 120;

/**
 * Schema do cadastro de consumidor.
 *
 * A data é validada como data real e maioridade (18+); o CEP é normalizado
 * para 8 dígitos (a máscara é apenas visual). As mensagens são chaves de
 * tradução, como nos demais formulários do projeto.
 */

export function normalizePostalCode(raw: string): string {
  return raw.replace(NON_DIGITS, "");
}

export function ageFromIsoDate(value: string, today = new Date()): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const birth = new Date(year, month - 1, day);
  if (birth.getFullYear() !== year || birth.getMonth() !== month - 1 || birth.getDate() !== day) {
    return null;
  }
  let age = today.getFullYear() - year;
  const beforeBirthday =
    today.getMonth() < month - 1 || (today.getMonth() === month - 1 && today.getDate() < day);
  if (beforeBirthday) {
    age -= 1;
  }
  return age;
}

export const registerConsumerFormSchema = z.object({
  full_name: z.string().trim().min(2, "consumer.fullNameRequired").max(200),
  email: z
    .string()
    .trim()
    .min(1, "auth.emailRequired")
    .max(320, "auth.emailTooLong")
    .email("auth.emailInvalid"),
  password: z.string().min(8, "onboarding.passwordMin").max(128, "onboarding.passwordMax"),
  birth_date: z
    .string()
    .min(1, "consumer.birthDateRequired")
    .refine((value) => ageFromIsoDate(value) !== null, "consumer.birthDateInvalid")
    .refine((value) => {
      const age = ageFromIsoDate(value);
      return age === null || age >= MIN_AGE;
    }, "consumer.birthDateMinAge")
    .refine((value) => {
      const age = ageFromIsoDate(value);
      return age === null || age <= MAX_AGE;
    }, "consumer.birthDateInvalid"),
  cpf: z
    .string()
    .trim()
    .min(1, "consumer.cpfRequired")
    .refine((value) => isValidCpf(value), "consumer.cpfInvalid"),
  postal_code: z
    .string()
    .trim()
    .min(1, "consumer.postalCodeRequired")
    .refine((value) => normalizePostalCode(value).length === 8, "consumer.postalCodeInvalid"),
  gender: z.enum(GENDERS, { errorMap: () => ({ message: "consumer.genderRequired" }) }),
  consent: z.boolean().refine((accepted) => accepted, "onboarding.consentRequired"),
});

export type RegisterConsumerFormValues = z.infer<typeof registerConsumerFormSchema>;
