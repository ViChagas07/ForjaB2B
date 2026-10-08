"use client";

import { useQuery } from "@tanstack/react-query";

import { creditApi } from "@/infrastructure/http";
import { withAuth } from "@/shared/lib/with-auth";
import { useAuthStore } from "@/shared/stores/auth-store";

/**
 * Hooks TanStack Query para o crédito (somente leitura: conta + ledger).
 */

export function useCreditAccount() {
  const status = useAuthStore((s) => s.status);
  return useQuery({
    queryKey: ["credit", "account"],
    queryFn: () => withAuth((token) => creditApi.getAccount(token)),
    enabled: status === "authenticated",
  });
}

export function useCreditEntries() {
  const status = useAuthStore((s) => s.status);
  return useQuery({
    queryKey: ["credit", "entries"],
    queryFn: () => withAuth((token) => creditApi.listEntries(token)),
    enabled: status === "authenticated",
  });
}
