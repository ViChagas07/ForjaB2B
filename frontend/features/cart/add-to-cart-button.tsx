"use client";

import * as React from "react";
import { ShoppingCart } from "lucide-react";
import { useTranslations } from "next-intl";

import { useAuthStore } from "@/shared/stores/auth-store";
import { Button } from "@/shared/ui/button";

import { AuthGateDialog } from "./auth-gate-dialog";
import { useAddCartItem } from "./hooks";

interface AddToCartButtonProps {
  productId: string;
  minQuantity?: number;
  quantity?: number;
  disabled?: boolean;
  className?: string;
  size?: "default" | "sm" | "lg" | "icon";
  variant?: "default" | "ink" | "secondary" | "outline" | "ghost" | "link" | "destructive";
}

/**
 * Adiciona um produto ao carrinho (mutação TanStack Query). Sem `quantity`
 * explícita, usa o lote mínimo (default 1); o backend valida de forma
 * definitiva a quantidade e a disponibilidade.
 *
 * O carrinho é tenant-scoped: visitantes podem navegar pelo catálogo, mas ao
 * tentar guardar um item recebem o convite para entrar/cadastrar a empresa.
 */
export function AddToCartButton({
  productId,
  minQuantity = 1,
  quantity,
  disabled,
  className,
  size = "default",
  variant = "ink",
}: AddToCartButtonProps) {
  const t = useTranslations();
  const status = useAuthStore((s) => s.status);
  const mutation = useAddCartItem();
  const [gateOpen, setGateOpen] = React.useState(false);

  const isAuthenticated = status === "authenticated";

  function handleClick() {
    if (!isAuthenticated) {
      setGateOpen(true);
      return;
    }
    mutation.mutate({ product_id: productId, quantity: quantity ?? minQuantity });
  }

  return (
    <>
      <Button
        size={size}
        variant={variant}
        className={className}
        disabled={disabled || mutation.isPending}
        onClick={handleClick}
      >
        <ShoppingCart aria-hidden="true" />
        {mutation.isPending ? t("loading") : t("catalog.addToCart")}
      </Button>

      <AuthGateDialog
        open={gateOpen}
        onOpenChange={setGateOpen}
        title={t("authGate.title")}
        description={t("authGate.description")}
      />
    </>
  );
}
