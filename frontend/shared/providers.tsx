"use client";

import * as React from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import { AuthInitializer } from "@/shared/components/auth-initializer";
import { ThemeProvider } from "@/shared/components/theme-provider";
import { getQueryClient } from "@/shared/lib/query-client";

/**
 * Providers do lado cliente. O QueryClient segue o padrão do App Router
 * (novo por requisição no servidor, singleton no navegador). O AuthInitializer
 * hidrata a sessão autenticada a partir do localStorage no cliente.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthInitializer />
        {children}
      </ThemeProvider>
    </QueryClientProvider>
  );
}
