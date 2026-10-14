"use client";

import { useQuery } from "@tanstack/react-query";

import { creditApi, useCreditApi } from "@/infrastructure/http";
import { withAuth } from "@/shared/lib/with-auth";
import { useAuthStore } from "@/shared/stores/auth-store";

/**
 * Hooks TanStack Query para o crédito (somente leitura: conta + ledger).
 */

export function useCreditAccount() {
  const status = useAuthStore((s) => s.status);
  const { getAccount } = useCreditApi();
  return useQuery({
    queryKey: ["credit", "account"],
    queryFn: () => withAuth((token) => getAccount(token)),
    enabled: status === "authenticated",
  });
}

export function useCreditEntries() {
  const status = useAuthStore((s) => s.status);
  const { listEntries } = useCreditApi();
  return useQuery({
    queryKey: ["credit", "entries"],
    queryFn: () => withAuth((token) => listEntries(token)),
    enabled: status === "authenticated",
  });
}
