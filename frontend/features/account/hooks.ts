"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AccountAvatar, AccountProfile, UpdateAccountInput } from "@/core/domain/account";
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

function applyAvatar(
  queryClient: ReturnType<typeof useQueryClient>,
  session: ReturnType<typeof useAuthStore.getState>["session"],
  setSession: ReturnType<typeof useAuthStore.getState>["setSession"],
  avatar: AccountAvatar,
): void {
  queryClient.setQueryData<AccountProfile | undefined>(ACCOUNT_KEY, (current) =>
    current ? { ...current, avatar_url: avatar.avatar_url } : current,
  );
  if (session) {
    setSession({
      ...session,
      user: { ...session.user, avatar_url: avatar.avatar_url },
    });
  }
}

export function useUploadAvatar() {
  const queryClient = useQueryClient();
  const session = useAuthStore((state) => state.session);
  const setSession = useAuthStore((state) => state.setSession);

  return useMutation({
    mutationFn: (file: File) => withAuth((token) => accountApi.uploadAvatar(token, file)),
    onSuccess: (avatar: AccountAvatar) => {
      applyAvatar(queryClient, session, setSession, avatar);
    },
  });
}

export function useRemoveAvatar() {
  const queryClient = useQueryClient();
  const session = useAuthStore((state) => state.session);
  const setSession = useAuthStore((state) => state.setSession);

  return useMutation({
    mutationFn: () => withAuth((token) => accountApi.removeAvatar(token)),
    onSuccess: (avatar: AccountAvatar) => {
      applyAvatar(queryClient, session, setSession, avatar);
    },
  });
}
