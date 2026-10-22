"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";

import type { InitiatePaymentInput, Payment, PaymentMethods } from "@/core/domain/payment";
import { usePaymentApi } from "@/infrastructure/http";
import { withAuth } from "@/shared/lib/with-auth";

/** Chave pública dos meios de pagamento (muda com o locale apenas por consistência). */
function paymentMethodsKey(locale: string) {
  return ["payments", "methods", locale] as const;
}

export function usePaymentMethods() {
  const locale = useLocale();
  const { methods } = usePaymentApi();
  return useQuery<PaymentMethods>({
    queryKey: paymentMethodsKey(locale),
    queryFn: methods,
    staleTime: 5 * 60_000,
  });
}

export function useInitiatePayment() {
  const { initiate } = usePaymentApi();
  return useMutation<Payment, unknown, InitiatePaymentInput>({
    mutationFn: (input) => withAuth((token) => initiate(token, input)),
  });
}
