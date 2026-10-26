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
 * Exibe um preco do catalogo. A regra de exposicao vem do backend
 * (`price_on_request`): produtos vendaveis trazem o preco de lista; produtos
 * bloqueados ou sem preco mostram "preco sob consulta". A exibicao tambem
 * protege contra um valor ausente por qualquer outro motivo.
 */
export function CatalogPrice({ amount, currency, priceOnRequest, className }: PriceProps) {
  const t = useTranslations();
  const locale = useLocale();

  if (priceOnRequest || amount == null) {
    return <span className={className}>{t("catalog.priceOnRequest")}</span>;
  }

  return <span className={className}>{formatMoney(amount, currency, locale)}</span>;
}
