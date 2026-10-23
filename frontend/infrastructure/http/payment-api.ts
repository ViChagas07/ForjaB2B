import type { InitiatePaymentInput, Payment, PaymentMethods } from "@/core/domain/payment";
import { useLocale } from "next-intl";

import { apiClient } from "./client";

/**
 * Adapter HTTP para pagamentos (`/api/v1/payments`).
 *
 * `methods` é público e informa se o cartão (Stripe) está habilitado no backend.
 * `initiate` é autenticado e devolve `checkout_url` para o redirect hospedado.
 */
export const paymentApi = {
  async methods(locale: string): Promise<PaymentMethods> {
    const response = await apiClient.request<PaymentMethods>({
      method: "GET",
      path: "/api/v1/payments/methods",
      locale,
    });
    return response.body;
  },

  async initiate(
    accessToken: string,
    input: InitiatePaymentInput,
    locale: string,
  ): Promise<Payment> {
    const response = await apiClient.request<Payment>({
      method: "POST",
      path: "/api/v1/payments",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Idempotency-Key": input.idempotency_key,
      },
      body: {
        order_id: input.order_id,
        method: input.method,
      },
      locale,
    });
    return response.body;
  },
};

export function usePaymentApi() {
  const locale = useLocale();
  return {
    methods: () => paymentApi.methods(locale),
    initiate: (token: string, input: InitiatePaymentInput) =>
      paymentApi.initiate(token, input, locale),
  };
}
