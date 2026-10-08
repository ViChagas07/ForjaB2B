"use client";

import { useLocale, useTranslations } from "next-intl";

import { formatMoney } from "@/shared/lib/money";
import { useAuthStore } from "@/shared/stores/auth-store";

interface PriceProps {
  amount: string;
  currency: string;
  className?: string;
}

/**
 * Exibe um preço do catálogo. Para usuários não autenticados, aplica a regra
 * de mascaramento ("preço sob consulta, apenas para CNPJ") — a mesma exibição
 * vale para produtos não vendáveis em qualquer público.
 */
export function CatalogPrice({ amount, currency, className }: PriceProps) {
  const t = useTranslations();
  const locale = useLocale();
  const isAuthenticated = useAuthStore((s) => s.status === "authenticated");

  if (!isAuthenticated) {
    return <span className={className}>{t("catalog.priceOnRequest")}</span>;
  }

  return <span className={className}>{formatMoney(amount, currency, locale)}</span>;
}
