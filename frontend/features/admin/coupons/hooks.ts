"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  AdminCouponCreate,
  AdminCouponListQuery,
  AdminCouponUpdate,
  CouponCodeResponse,
} from "@/core/domain/coupons";
import { adminCouponsApi } from "@/infrastructure/http";
import { withAuth } from "@/shared/lib/with-auth";
import { useAuthStore } from "@/shared/stores/auth-store";

const ROOT = ["admin", "coupons"] as const;

export function couponListKey(filters: AdminCouponListQuery) {
  return [...ROOT, "list", filters] as const;
}

export function couponDetailKey(couponId: string) {
  return [...ROOT, "detail", couponId] as const;
}

export function useAdminCoupons(filters: AdminCouponListQuery) {
  const session = useAuthStore((state) => state.session);
  const status = useAuthStore((state) => state.status);
  return useQuery({
    queryKey: couponListKey(filters),
    queryFn: () => withAuth((token) => adminCouponsApi.list(token, filters)),
    enabled: status === "authenticated" && session?.user.role === "ADMIN",
  });
}

export function useAdminCoupon(couponId: string | null) {
  const session = useAuthStore((state) => state.session);
  const status = useAuthStore((state) => state.status);
  return useQuery({
    queryKey: couponDetailKey(couponId ?? ""),
    queryFn: () => withAuth((token) => adminCouponsApi.get(token, couponId!)),
    enabled: Boolean(couponId) && status === "authenticated" && session?.user.role === "ADMIN",
  });
}

export function useCreateCoupon() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdminCouponCreate) =>
      withAuth((token) => adminCouponsApi.create(token, payload)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ROOT });
    },
  });
}

export function useUpdateCoupon(couponId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdminCouponUpdate) =>
      withAuth((token) => adminCouponsApi.update(token, couponId ?? "", payload)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ROOT });
    },
  });
}

export function useToggleCoupon() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ couponId, isActive }: { couponId: string; isActive: boolean }) =>
      withAuth((token) => adminCouponsApi.update(token, couponId, { is_active: isActive })),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ROOT });
    },
  });
}

export function useGenerateCouponCode() {
  return useMutation<CouponCodeResponse, Error, void>({
    mutationFn: () => withAuth((token) => adminCouponsApi.generateCode(token)),
  });
}
