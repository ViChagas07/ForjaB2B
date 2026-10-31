"use client";

import * as React from "react";
import { Check } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import {
  SUPPORTED_CURRENCIES,
  type CurrencyCode,
  type CurrencyRates,
} from "@/core/domain/currency";
import { isRtlLocale } from "@/i18n/locales";
import { useCurrency } from "@/shared/components/currency-provider";
import {
  formatRateDate,
  formatUnitRateInBrl,
  getCurrencyDisplayName,
  getCurrencySymbol,
} from "@/shared/lib/money";
import { cn } from "@/shared/lib/utils";
import { Card, CardContent } from "@/shared/ui/card";

function hasUsableRate(code: CurrencyCode, rates: CurrencyRates): boolean {
  if (code === "BRL") return true;
  const raw = rates[code];
  return raw !== undefined && Number.isFinite(Number(raw)) && Number(raw) > 0;
}

/**
 * Secao "Moeda" das Configuracoes.
 *
 * Replica o padrao visual da grade de idiomas, mas usa um radiogroup real:
 * setas movem a selecao, Home/End vao aos extremos e o padrao RTL inverte as
 * setas horizontais. Opcoes sem taxa ficam desabilitadas e a selecao cai em
 * BRL, nunca em uma moeda que a UI nao consegue converter.
 */
export function CurrencySettingsSection() {
  const t = useTranslations("settings");
  const tc = useTranslations("currency");
  const locale = useLocale();
  const { currency, rates, rateDate, source, stale, setCurrency } = useCurrency();
  const optionRefs = React.useRef<Partial<Record<CurrencyCode, HTMLButtonElement | null>>>({});

  const options = SUPPORTED_CURRENCIES.map((code) => ({
    code,
    disabled: !hasUsableRate(code, rates),
  }));
  const enabledOptions = options.filter((option) => !option.disabled);
  const hasAnyRate = enabledOptions.some((option) => option.code !== "BRL");

  function handleKeyDown(
    event: React.KeyboardEvent<HTMLButtonElement>,
    currentCode: CurrencyCode,
  ): void {
    const currentIndex = enabledOptions.findIndex((option) => option.code === currentCode);
    if (currentIndex < 0) return;

    const rtl = isRtlLocale(locale);
    let nextIndex = currentIndex;
    switch (event.key) {
      case "ArrowRight":
        nextIndex = rtl ? currentIndex - 1 : currentIndex + 1;
        break;
      case "ArrowLeft":
        nextIndex = rtl ? currentIndex + 1 : currentIndex - 1;
        break;
      case "ArrowDown":
        nextIndex = currentIndex + 1;
        break;
      case "ArrowUp":
        nextIndex = currentIndex - 1;
        break;
      case "Home":
        nextIndex = 0;
        break;
      case "End":
        nextIndex = enabledOptions.length - 1;
        break;
      default:
        return;
    }

    event.preventDefault();
    const target = enabledOptions[(nextIndex + enabledOptions.length) % enabledOptions.length];
    if (!target) return;
    setCurrency(target.code);
    optionRefs.current[target.code]?.focus();
  }

  return (
    <section id="currency" className="scroll-mt-24 space-y-4">
      <h2 className="text-xl font-bold">{t("currency")}</h2>
      <Card>
        <CardContent className="space-y-4 p-5">
          <p className="text-sm text-muted-foreground">{t("currencyDescription")}</p>

          {hasAnyRate ? null : (
            <p
              role="status"
              className="rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm text-foreground"
            >
              {tc("unavailable")}
            </p>
          )}

          <div role="radiogroup" aria-label={t("currency")} className="grid gap-3 sm:grid-cols-2">
            {options.map((option) => {
              const selected = option.code === currency;
              return (
                <button
                  key={option.code}
                  ref={(element) => {
                    optionRefs.current[option.code] = element;
                  }}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  disabled={option.disabled}
                  tabIndex={selected ? 0 : -1}
                  onClick={() => setCurrency(option.code)}
                  onKeyDown={(event) => handleKeyDown(event, option.code)}
                  className={cn(
                    "flex items-center justify-between gap-3 rounded-xl border-2 px-4 py-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                    selected
                      ? "border-primary bg-primary/10"
                      : "border-border bg-card hover:border-primary/50",
                    option.disabled && "cursor-not-allowed opacity-50 hover:border-border",
                  )}
                >
                  <span className="flex min-w-0 items-center gap-3">
                    <span className="shrink-0 font-mono text-xs tracking-wide text-muted-foreground">
                      {option.code}
                    </span>
                    <span className="truncate">{getCurrencyDisplayName(option.code, locale)}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    <span aria-hidden="true" className="text-base font-semibold">
                      {getCurrencySymbol(option.code, locale)}
                    </span>
                    {selected ? (
                      <Check aria-hidden="true" className="h-4 w-4 text-foreground" />
                    ) : null}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="space-y-2 rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">
            <p>{tc("approximate")}</p>
            <p>{tc("chargesInBrl")}</p>
            {hasAnyRate ? (
              <p>
                {tc("rateDisclosure", {
                  source: source ?? "—",
                  date: rateDate ? formatRateDate(rateDate, locale) : "—",
                })}
              </p>
            ) : null}
            {stale && hasAnyRate ? (
              <p className="font-medium text-foreground">{tc("rateStale")}</p>
            ) : null}
            {currency !== "BRL" ? (
              <p className="font-semibold text-foreground">
                {formatUnitRateInBrl(currency, rates, locale)}
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
