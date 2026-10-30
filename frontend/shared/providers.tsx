"use client";

import * as React from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import type { CurrencyBootstrap } from "@/core/domain/currency";
import { AuthInitializer } from "@/shared/components/auth-initializer";
import { CurrencyProvider } from "@/shared/components/currency-provider";
import { ThemeProvider } from "@/shared/components/theme-provider";
import { getQueryClient } from "@/shared/lib/query-client";

/**
 * Providers do lado cliente. O QueryClient segue o padrão do App Router
 * (novo por requisição no servidor, singleton no navegador). O AuthInitializer
 * hidrata a sessão autenticada a partir do localStorage no cliente.
 *
 * A moeda chega pronta do layout (cookie validado + taxas do backend) para que
 * servidor e cliente pintem exatamente o mesmo estado no primeiro render.
 */
export function Providers({
  children,
  initialCurrency,
}: {
  children: React.ReactNode;
  initialCurrency: CurrencyBootstrap;
}) {
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <CurrencyProvider initial={initialCurrency}>
        <ThemeProvider>
          <AuthInitializer />
          {children}
        </ThemeProvider>
      </CurrencyProvider>
    </QueryClientProvider>
  );
}
