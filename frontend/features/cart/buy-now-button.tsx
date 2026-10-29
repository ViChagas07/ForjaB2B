"use client";

import * as React from "react";
import { ShoppingBag } from "lucide-react";
import { useTranslations } from "next-intl";

import { useRouter } from "@/i18n/navigation";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Button } from "@/shared/ui/button";

import { AuthGateDialog } from "./auth-gate-dialog";
import { useAddCartItem } from "./hooks";

interface BuyNowButtonProps {
  productId: string;
  minQuantity?: number;
  quantity?: number;
  disabled?: boolean;
  className?: string;
  size?: "default" | "sm" | "lg" | "icon";
}

/**
 * Compra direta: adiciona o produto ao carrinho e leva ao checkout. Exige
 * sessão autenticada, como o restante do fluxo de carrinho/pedido.
 */
export function BuyNowButton({
  productId,
  minQuantity = 1,
  quantity,
  disabled,
  className,
  size = "default",
}: BuyNowButtonProps) {
  const t = useTranslations();
  const router = useRouter();
  const status = useAuthStore((s) => s.status);
  const mutation = useAddCartItem();
  const [gateOpen, setGateOpen] = React.useState(false);

  const isAuthenticated = status === "authenticated";

  function handleClick() {
    if (!isAuthenticated) {
      setGateOpen(true);
      return;
    }
    mutation.mutate(
      { product_id: productId, quantity: quantity ?? minQuantity },
      { onSuccess: () => router.push("/checkout") },
    );
  }

  return (
    <>
      <Button
        size={size}
        className={className}
        disabled={disabled || mutation.isPending}
        onClick={handleClick}
      >
        <ShoppingBag aria-hidden="true" />
        {mutation.isPending ? t("loading") : t("catalog.buyNow")}
      </Button>

      <AuthGateDialog
        open={gateOpen}
        onOpenChange={setGateOpen}
        title={t("authGate.buyTitle")}
        description={t("authGate.buyDescription")}
      />
    </>
  );
}
