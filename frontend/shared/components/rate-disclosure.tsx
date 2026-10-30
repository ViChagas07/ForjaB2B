"use client";

import { useLocale, useTranslations } from "next-intl";

import { formatRateDate } from "@/shared/lib/money";
import { cn } from "@/shared/lib/utils";

import { useCurrency } from "./currency-provider";

/**
 * Transparência da taxa: fonte, data de referência e aviso de desatualização.
 *
 * Fica oculto quando a moeda efetiva é BRL (não há conversão a explicar).
 * A data exibida é a `rate_date` devolvida pela Frankfurter, não o instante
 * em que o servidor consultou a API.
 */
export function RateDisclosure({ className }: { className?: string }) {
  const t = useTranslations("currency");
  const locale = useLocale();
  const { currency, rateDate, source, stale } = useCurrency();

  if (currency === "BRL") return null;

  const dateLabel = rateDate ? formatRateDate(rateDate, locale) : "—";
  const sourceLabel = source ?? "—";

  return (
    <div
      data-testid="rate-disclosure"
      className={cn(
        "rounded-xl border border-border bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground",
        className,
      )}
    >
      <p>{t("rateDisclosure", { source: sourceLabel, date: dateLabel })}</p>
      {stale ? <p className="mt-1 font-medium text-warning">{t("rateStale")}</p> : null}
    </div>
  );
}
