"use client";

import { useLocale, useTranslations } from "next-intl";

import { formatBrl, formatMoney } from "@/shared/lib/money";
import { cn } from "@/shared/lib/utils";

import { useCurrency } from "./currency-provider";

export interface PriceDisplayProps {
  amount: string | number | null;
  /** `converted` para catálogo/produto/carrinho; `brl` para checkout/pedidos. */
  primary?: "converted" | "brl";
  /** Linha secundária: BRL da cobrança ou valor aproximado, conforme o modo. */
  showSecondary?: boolean;
  className?: string;
  secondaryClassName?: string;
}

/**
 * Exibição padronizada de um valor BRL vindo do backend.
 *
 * - `primary="converted"`: mostra a moeda escolhida com ≈ e, se pedido, a
 *   cobrança real em R$ na linha secundária.
 * - `primary="brl"`: mostra R$ (o valor efetivamente cobrado) e, se pedido, a
 *   conversão aproximada na linha secundária.
 *
 * Nenhum total, cupom ou frete é recalculado aqui: a entrada é sempre o valor
 * em BRL devolvido pela API.
 */
export function PriceDisplay({
  amount,
  primary = "converted",
  showSecondary = false,
  className,
  secondaryClassName,
}: PriceDisplayProps) {
  const t = useTranslations("currency");
  const locale = useLocale();
  const { currency, rates } = useCurrency();

  if (amount === null) return null;

  const brl = formatBrl(amount, locale);
  const canConvert = currency !== "BRL";
  const converted = canConvert ? formatMoney(amount, { currency, locale, rates }) : brl;
  const primaryText = primary === "brl" || !canConvert ? brl : converted;
  const secondaryText =
    showSecondary && canConvert
      ? primary === "brl"
        ? converted
        : t("chargeIn", { value: brl })
      : null;

  return (
    <span className={className}>
      <span className="block">{primaryText}</span>
      {secondaryText ? (
        <span
          className={cn(
            "mt-0.5 block text-xs font-normal text-muted-foreground",
            secondaryClassName,
          )}
        >
          {secondaryText}
        </span>
      ) : null}
    </span>
  );
}
