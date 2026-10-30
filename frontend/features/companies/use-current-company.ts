"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { useCompanyApi, problemCode } from "@/infrastructure/http";
import { refreshSession } from "@/shared/stores/auth-actions";
import { useAuthStore } from "@/shared/stores/auth-store";

/**
 * Fonte de verdade do tipo de conta no cliente.
 *
 * A sessão pode ter sido criada antes do campo `account_type` (ou por um
 * response antigo do OAuth). `/companies/me` sempre reflete o tenant atual,
 * então sincronizamos a sessão com ele. O query key inclui o usuário para
 * nunca reutilizar dados de outra conta após logout/login.
 */
export function useCurrentCompany() {
  const status = useAuthStore((state) => state.status);
  const session = useAuthStore((state) => state.session);
  const { getMe } = useCompanyApi();

  const query = useQuery({
    queryKey: ["company", "me", session?.user.id],
    enabled: status === "authenticated" && Boolean(session),
    queryFn: async () => {
      const token = useAuthStore.getState().session?.access_token;
      if (!token) {
        throw new Error("unauthenticated");
      }
      try {
        return await getMe(token);
      } catch (error) {
        const code = problemCode(error);
        if (code === "token_expired" || code === "invalid_token") {
          await refreshSession();
          const newToken = useAuthStore.getState().session?.access_token;
          if (newToken) {
            return getMe(newToken);
          }
        }
        throw error;
      }
    },
  });

  React.useEffect(() => {
    const company = query.data;
    if (!company) return;
    const current = useAuthStore.getState().session;
    if (!current || current.user.account_type === company.account_type) return;
    useAuthStore.getState().setSession({
      ...current,
      user: { ...current.user, account_type: company.account_type },
    });
  }, [query.data]);

  return query;
}
