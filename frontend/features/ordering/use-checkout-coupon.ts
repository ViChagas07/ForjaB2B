"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";

import {
  COUPON_REJECTION_REASONS,
  type CouponPreview,
  type CouponRejectionReason,
  type PaymentMethod,
} from "@/core/domain/ordering";
import { problemCode, useOrderingApi } from "@/infrastructure/http";
import { withAuth } from "@/shared/lib/with-auth";

export type CouponUiReason = CouponRejectionReason | "CODE_REQUIRED" | "GENERIC";

export interface CouponUiError {
  reason: CouponUiReason;
  missingAmount: string | null;
}

interface UseCheckoutCouponArgs {
  paymentMethod: PaymentMethod;
  cartSignature: string;
  hasItems: boolean;
  orderError: unknown;
}

function isRejectionReason(value: string): value is CouponRejectionReason {
  return (COUPON_REJECTION_REASONS as readonly string[]).includes(value);
}

/**
 * Estado do cupom no checkout.
 *
 * Duas consultas de previa: uma sem codigo (resumo base) e outra com o codigo
 * candidato/aplicado. O codigo entra na query key junto de pagamento e do
 * carrinho; qualquer mudanca revalida automaticamente no backend.
 */
export function useCheckoutCoupon({
  paymentMethod,
  cartSignature,
  hasItems,
  orderError,
}: UseCheckoutCouponArgs) {
  const { previewCoupon } = useOrderingApi();
  const locale = useLocale();
  const [expanded, setExpanded] = React.useState(false);
  const [input, setInput] = React.useState("");
  const [candidateCode, setCandidateCode] = React.useState<string | null>(null);
  const [appliedCode, setAppliedCode] = React.useState<string | null>(null);
  const [appliedPreview, setAppliedPreview] = React.useState<CouponPreview | null>(null);
  const [error, setError] = React.useState<CouponUiError | null>(null);

  const baseQuery = useQuery<CouponPreview>({
    queryKey: ["checkout-coupon", "base", paymentMethod, cartSignature, locale],
    queryFn: () =>
      withAuth((token) => previewCoupon(token, { code: null, payment_method: paymentMethod })),
    enabled: hasItems,
    retry: false,
    staleTime: 0,
    refetchOnWindowFocus: false,
    placeholderData: (previous) => previous,
  });

  const candidateQuery = useQuery<CouponPreview>({
    queryKey: ["checkout-coupon", candidateCode, paymentMethod, cartSignature, locale],
    queryFn: () =>
      withAuth((token) =>
        previewCoupon(token, {
          code: candidateCode,
          payment_method: paymentMethod,
        }),
      ),
    enabled: hasItems && candidateCode !== null,
    retry: false,
    staleTime: 0,
    refetchOnWindowFocus: false,
  });

  React.useEffect(() => {
    if (candidateCode === null) return;
    if (candidateQuery.isError) {
      setError({ reason: "GENERIC", missingAmount: null });
      setAppliedCode(null);
      setAppliedPreview(null);
      setCandidateCode(null);
      setExpanded(true);
      return;
    }
    const preview = candidateQuery.data;
    if (!preview) return;
    if (preview.valid) {
      setAppliedCode(candidateCode);
      setAppliedPreview(preview);
      setError(null);
      return;
    }
    setAppliedCode(null);
    setAppliedPreview(null);
    setError({
      reason: preview.reason ?? "GENERIC",
      missingAmount: preview.missing_amount,
    });
    setCandidateCode(null);
    setExpanded(true);
  }, [candidateCode, candidateQuery.data, candidateQuery.isError]);

  React.useEffect(() => {
    const code = problemCode(orderError);
    if (!code?.startsWith("coupon_")) return;
    const reason = code.slice("coupon_".length).toUpperCase();
    if (!isRejectionReason(reason)) return;
    setAppliedCode(null);
    setAppliedPreview(null);
    setCandidateCode(null);
    setError({ reason, missingAmount: null });
    setExpanded(true);
  }, [orderError]);

  const preview = appliedCode
    ? (candidateQuery.data ?? appliedPreview ?? baseQuery.data)
    : baseQuery.data;
  const isLoading = candidateCode !== null && appliedCode === null && candidateQuery.isFetching;
  const isRevalidating = Boolean(appliedCode) && candidateQuery.isFetching;

  function apply() {
    const normalized = input.trim().toUpperCase();
    if (!normalized) {
      setError({ reason: "CODE_REQUIRED", missingAmount: null });
      setExpanded(true);
      return;
    }
    setInput(normalized);
    setError(null);
    if (normalized === candidateCode) {
      void candidateQuery.refetch();
      return;
    }
    setCandidateCode(normalized);
  }

  function remove() {
    setCandidateCode(null);
    setAppliedCode(null);
    setAppliedPreview(null);
    setInput("");
    setError(null);
    setExpanded(false);
  }

  function toggle() {
    setExpanded((current) => {
      const next = !current;
      if (!next) setError(null);
      return next;
    });
  }

  return {
    expanded,
    input,
    setInput,
    appliedCode,
    preview,
    isLoading,
    isRevalidating,
    error,
    apply,
    remove,
    toggle,
    setExpanded,
  };
}
