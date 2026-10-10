"use client";

import { useLocale, useTranslations } from "next-intl";

import { formatMoney } from "@/shared/lib/money";

interface PriceProps {
  amount: string | null;
  currency: string;
  priceOnRequest: boolean;
  className?: string;
}

/**
 * Exibe um preço do catálogo. A regra de preço consultivo vem do backend
 * (`price_on_request`): para visitante o valor é nulo e mostramos
 * "preço sob consulta, apenas para CNPJ". A exibição também protege contra um
 * valor ausente por qualquer outro motivo.
 */
export function CatalogPrice({ amount, currency, priceOnRequest, className }: PriceProps) {
  const t = useTranslations();
  const locale = useLocale();

  if (priceOnRequest || amount == null) {
    return <span className={className}>{t("catalog.priceOnRequest")}</span>;
  }

  return <span className={className}>{formatMoney(amount, currency, locale)}</span>;
}
