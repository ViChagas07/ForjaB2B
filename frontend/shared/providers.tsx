"use client";

import * as React from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import { AuthInitializer } from "@/shared/components/auth-initializer";
import { ThemeProvider } from "@/shared/components/theme-provider";
import { createQueryClient } from "@/shared/lib/query-client";

/**
 * Providers do lado cliente. O QueryClient é criado uma única vez por sessão
 * de navegação (useState) e fornecido ao TanStack Query. O AuthInitializer
 * hidrata a sessão autenticada a partir do localStorage no cliente.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(() => createQueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthInitializer />
        {children}
      </ThemeProvider>
    </QueryClientProvider>
  );
}
