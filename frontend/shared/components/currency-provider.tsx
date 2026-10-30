"use client";

import * as React from "react";

import {
  effectiveCurrency,
  normalizeCurrency,
  type CurrencyBootstrap,
  type CurrencyCode,
} from "@/core/domain/currency";
import { writeCurrencyCookie } from "@/shared/lib/currency-cookie";

export interface CurrencyContextValue extends CurrencyBootstrap {
  setCurrency: (currency: CurrencyCode) => void;
}

const CurrencyContext = React.createContext<CurrencyContextValue | null>(null);

/**
 * Preferência de exibição vinda do servidor.
 *
 * `initial` já chega resolvido (cookie validado + taxas do endpoint) para que
 * o primeiro paint do servidor e do cliente seja idêntico. O provider não lê
 * cookie nem faz fetch no cliente; `setCurrency` apenas atualiza o estado e
 * grava o cookie para as próximas renderizações do servidor.
 */
export function CurrencyProvider({
  children,
  initial,
}: {
  children: React.ReactNode;
  initial: CurrencyBootstrap;
}) {
  const [state, setState] = React.useState<CurrencyBootstrap>(() => ({
    ...initial,
    currency: effectiveCurrency(initial.currency, initial.rates),
  }));

  const setCurrency = React.useCallback((next: CurrencyCode) => {
    const normalized = normalizeCurrency(next);
    setState((previous) => ({
      ...previous,
      currency: effectiveCurrency(normalized, previous.rates),
    }));
    writeCurrencyCookie(normalized);
  }, []);

  const value = React.useMemo<CurrencyContextValue>(
    () => ({ ...state, setCurrency }),
    [state, setCurrency],
  );

  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>;
}

export function useCurrency(): CurrencyContextValue {
  const context = React.useContext(CurrencyContext);
  if (context === null) {
    throw new Error("useCurrency deve ser usado dentro de CurrencyProvider");
  }
  return context;
}
