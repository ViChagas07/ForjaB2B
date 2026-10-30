"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AccountProfile, UpdateAccountInput } from "@/core/domain/account";
import { accountApi } from "@/infrastructure/http";
import { withAuth } from "@/shared/lib/with-auth";
import { useAuthStore } from "@/shared/stores/auth-store";

const ACCOUNT_KEY = ["account"] as const;

export function useAccount() {
  const status = useAuthStore((state) => state.status);
  return useQuery({
    queryKey: ACCOUNT_KEY,
    queryFn: () => withAuth((token) => accountApi.get(token)),
    enabled: status === "authenticated",
  });
}

export function useUpdateAccount() {
  const queryClient = useQueryClient();
  const session = useAuthStore((state) => state.session);
  const setSession = useAuthStore((state) => state.setSession);

  return useMutation({
    mutationFn: (input: UpdateAccountInput) => withAuth((token) => accountApi.update(token, input)),
    onSuccess: (profile: AccountProfile) => {
      queryClient.setQueryData(ACCOUNT_KEY, profile);
      if (session) {
        setSession({
          ...session,
          user: { ...session.user, full_name: profile.full_name },
        });
      }
    },
  });
}
