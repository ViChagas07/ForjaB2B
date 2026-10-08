"use client";

import { useTranslations } from "next-intl";
import { ShoppingCart } from "lucide-react";

import { Button } from "@/shared/ui/button";
import { useAddCartItem } from "./hooks";

interface AddToCartButtonProps {
  productId: string;
  minQuantity?: number;
  disabled?: boolean;
  className?: string;
  size?: "default" | "sm" | "lg" | "icon";
  variant?: "default" | "secondary" | "outline" | "ghost" | "link" | "destructive";
}

/**
 * Adiciona um produto ao carrinho (mutação TanStack Query). Lote mínimo é
 * refletido no payload (default 1); o backend valida de forma definitiva.
 */
export function AddToCartButton({
  productId,
  minQuantity = 1,
  disabled,
  className,
  size = "default",
  variant = "default",
}: AddToCartButtonProps) {
  const t = useTranslations();
  const mutation = useAddCartItem();

  return (
    <Button
      size={size}
      variant={variant}
      className={className}
      disabled={disabled || mutation.isPending}
      onClick={() => mutation.mutate({ product_id: productId, quantity: minQuantity })}
    >
      <ShoppingCart aria-hidden="true" />
      {mutation.isPending ? t("loading") : t("catalog.addToCart")}
    </Button>
  );
}
