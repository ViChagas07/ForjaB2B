"use client";

import { useTranslations } from "next-intl";

import { PriceDisplay } from "@/shared/components/price-display";

interface PriceProps {
  amount: string | null;
  priceOnRequest: boolean;
  showBrl?: boolean;
  className?: string;
}

/**
 * Exibe um preco do catalogo convertido para a moeda de exibicao.
 *
 * A regra de exposicao vem do backend (`price_on_request`): produtos vendaveis
 * trazem o preco de lista em BRL; produtos bloqueados ou sem preco mostram
 * "preco sob consulta". No detalhe do produto, `showBrl` acrescenta a linha
 * secundaria com a cobranca real em reais.
 */
export function CatalogPrice({ amount, priceOnRequest, showBrl, className }: PriceProps) {
  const t = useTranslations();

  if (priceOnRequest || amount == null) {
    return <span className={className}>{t("catalog.priceOnRequest")}</span>;
  }

  return (
    <PriceDisplay
      amount={amount}
      primary="converted"
      showSecondary={showBrl}
      className={className}
    />
  );
}
