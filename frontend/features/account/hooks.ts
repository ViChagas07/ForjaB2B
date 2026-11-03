"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AccountAvatar, AccountProfile, UpdateAccountInput } from "@/core/domain/account";
import { accountApi, authApi } from "@/infrastructure/http";
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

export function useUpdateSpendingVisibility() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (hideSpending: boolean) =>
      withAuth((token) => accountApi.updateSpendingVisibility(token, hideSpending)),
    onSuccess: (preferences) => {
      queryClient.setQueryData<AccountProfile | undefined>(ACCOUNT_KEY, (current) =>
        current ? { ...current, hide_spending: preferences.hide_spending } : current,
      );
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


const PHONE_VERIFICATION_KEY = ["account", "phone-verification"] as const;

export function usePhoneVerificationStatus() {
  const status = useAuthStore((state) => state.status);
  return useQuery({
    queryKey: PHONE_VERIFICATION_KEY,
    queryFn: () => withAuth((token) => authApi.getPhoneVerificationStatus(token)),
    enabled: status === "authenticated",
  });
}

export function useStartPhoneVerification() {
  return useMutation({
    mutationFn: ({ phone, locale }: { phone: string; locale: string }) =>
      withAuth((token) => authApi.startPhoneVerification(token, phone, locale)),
  });
}

export function useCheckPhoneVerification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ phone, code }: { phone: string; code: string }) =>
      withAuth((token) => authApi.checkPhoneVerification(token, phone, code)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PHONE_VERIFICATION_KEY });
      void queryClient.invalidateQueries({ queryKey: ACCOUNT_KEY });
    },
  });
}
