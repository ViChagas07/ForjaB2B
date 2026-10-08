import { z } from "zod";

import { isValidCnpj, isValidCpf } from "@/core/domain";

/**
 * Schema de validação do formulário de onboarding (empresa + operador inicial).
 *
 * As mensagens são chaves de tradução. CNPJ/CPF são validados estruturalmente
 * (dígitos verificadores) com os mesmos algoritmos do domínio; senha exige o
 * mínimo do backend (8 caracteres). Limites de tamanho espelham o contrato
 * `RegisterCompanyRequest`.
 */

export const registerCompanyFormSchema = z.object({
  cnpj: z
    .string()
    .trim()
    .min(1, "onboarding.cnpjRequired")
    .refine((value) => isValidCnpj(value), "onboarding.cnpjInvalid"),
  legal_name: z.string().trim().min(2, "onboarding.legalNameRequired").max(200),
  trade_name: z.string().trim().max(200).optional(),
  admin_full_name: z.string().trim().min(2, "onboarding.adminFullNameRequired").max(200),
  admin_email: z
    .string()
    .trim()
    .min(1, "onboarding.adminEmailRequired")
    .max(320)
    .email("onboarding.adminEmailInvalid"),
  admin_cpf: z
    .string()
    .trim()
    .min(1, "onboarding.adminCpfRequired")
    .refine((value) => isValidCpf(value), "onboarding.adminCpfInvalid"),
  password: z.string().min(8, "onboarding.passwordMin").max(128, "onboarding.passwordMax"),
});

export type RegisterCompanyFormValues = z.infer<typeof registerCompanyFormSchema>;
