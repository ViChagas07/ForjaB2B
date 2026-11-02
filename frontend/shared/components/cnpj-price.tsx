"use client";

import { useLocale, useTranslations } from "next-intl";

import { formatNumber } from "@/shared/lib/money";
import { cn } from "@/shared/lib/utils";

import { PriceDisplay } from "./price-display";

export function CnpjDiscountBadge({
  percent,
  className,
}: {
  percent: string | number;
  className?: string;
}) {
  const t = useTranslations();
  const locale = useLocale();
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full bg-accent px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-accent-foreground",
        className,
      )}
    >
      {t("catalog.cnpjBadge", { percent: formatNumber(Number(percent), locale) })}
    </span>
  );
}

export function CnpjVolumeNotice({
  unitsToVolume,
  band,
  className,
}: {
  unitsToVolume?: number | null;
  band?: number | null;
  className?: string;
}) {
  const t = useTranslations();
  if (unitsToVolume != null && unitsToVolume > 0) {
    return (
      <p className={cn("text-xs leading-relaxed text-muted-foreground", className)}>
        {t("cart.cnpjVolumeRemaining", { count: unitsToVolume })}
      </p>
    );
  }
  if (band === 30) {
    return (
      <p className={cn("text-xs font-semibold leading-relaxed text-success", className)}>
        {t("cart.cnpjVolumeReached")}
      </p>
    );
  }
  return null;
}

interface CnpjPriceProps {
  /** Preco de tabela antes do desconto CNPJ (vindo da API). */
  listAmount?: string | null;
  /** Preco final com o desconto CNPJ (vindo da API). */
  finalAmount?: string | null;
  /** Percentual aplicado (15 ou 30), tambem vindo da API. */
  percent?: string | number | null;
  /** Mostra a cobranca real em BRL como linha secundaria. */
  showBrl?: boolean;
  /** Moeda principal: convertida (catalogo/carrinho) ou BRL (checkout/pedido). */
  primary?: "converted" | "brl";
  /** Aviso de volume (catalogo/produto). */
  showVolumeHint?: boolean;
  className?: string;
  priceClassName?: string;
}

/**
 * Exibe o preco de tabela riscado e o preco final com desconto CNPJ.
 *
 * Todos os valores e o percentual vem prontos da API: o componente apenas
 * formata/converte para a moeda de exibicao, nunca recalcula preco. Para
 * usuarios nao-CNPJ (ou sem desconto), cai no `PriceDisplay` normal.
 */
export function CnpjPrice({
  listAmount,
  finalAmount,
  percent,
  showBrl = false,
  primary = "converted",
  showVolumeHint = false,
  className,
  priceClassName,
}: CnpjPriceProps) {
  const t = useTranslations();
  const numericPercent = Number(percent ?? 0);
  const hasDiscount =
    Number.isFinite(numericPercent) &&
    numericPercent > 0 &&
    listAmount != null &&
    finalAmount != null;

  if (!hasDiscount) {
    return (
      <PriceDisplay
        amount={finalAmount ?? listAmount ?? null}
        primary={primary}
        showSecondary={showBrl}
        className={priceClassName}
      />
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <CnpjDiscountBadge percent={numericPercent} />
        <s className="text-xs text-muted-foreground">
          <span className="sr-only">{t("catalog.listPrice")}: </span>
          <PriceDisplay amount={listAmount} primary={primary} />
        </s>
      </div>
      <PriceDisplay
        amount={finalAmount}
        primary={primary}
        showSecondary={showBrl}
        className={priceClassName}
      />
      {showVolumeHint ? (
        <p className="text-xs leading-relaxed text-muted-foreground">
          {t("catalog.cnpjVolumeHint")}
        </p>
      ) : null}
    </div>
  );
}
