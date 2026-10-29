import type { RegisterConsumerInput, RegisterConsumerResult } from "@/core/domain/consumer";
import { useLocale } from "next-intl";

import { apiClient } from "./client";

/**
 * Adapter HTTP do cadastro de consumidor (`POST /api/v1/consumers`).
 *
 * O backend valida CPF, idade, CEP e consentimento; o frontend apenas envia
 * os dados normalizados (CPF/CEP sem máscara, data em ISO).
 */
export const consumerApi = {
  async register(input: RegisterConsumerInput, locale: string): Promise<RegisterConsumerResult> {
    const response = await apiClient.request<RegisterConsumerResult>({
      method: "POST",
      path: "/consumers",
      body: {
        full_name: input.full_name,
        email: input.email,
        password: input.password,
        cpf: input.cpf,
        birth_date: input.birth_date,
        postal_code: input.postal_code,
        gender: input.gender,
        consent: input.consent,
      },
      locale,
    });
    return response.body;
  },
};

/** Hook para obter as funções da API com o locale atual automaticamente. */
export function useConsumerApi() {
  const locale = useLocale();
  return {
    register: (input: RegisterConsumerInput) => consumerApi.register(input, locale),
  };
}
