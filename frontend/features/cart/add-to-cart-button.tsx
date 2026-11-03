"use client";

import * as React from "react";
import { CircleCheck, ShoppingCart } from "lucide-react";
import { useTranslations } from "next-intl";

import { cn } from "@/shared/lib/utils";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Button } from "@/shared/ui/button";

import { AuthGateDialog } from "./auth-gate-dialog";
import { useAddCartItem } from "./hooks";

const SUCCESS_DURATION_MS = 3000;

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
  const [added, setAdded] = React.useState(false);
  const resetTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const isAuthenticated = status === "authenticated";
  const showSuccess = added && !mutation.isPending;

  React.useEffect(() => {
    return () => {
      if (resetTimer.current) {
        clearTimeout(resetTimer.current);
      }
    };
  }, []);

  function handleSuccess() {
    setAdded(true);
    if (resetTimer.current) {
      clearTimeout(resetTimer.current);
    }
    resetTimer.current = setTimeout(() => setAdded(false), SUCCESS_DURATION_MS);
  }

  function handleClick() {
    if (!isAuthenticated) {
      setGateOpen(true);
      return;
    }
    mutation.mutate(
      { product_id: productId, quantity: quantity ?? minQuantity },
      { onSuccess: handleSuccess },
    );
  }

  return (
    <>
      <Button
        size={size}
        variant={variant}
        className={cn(
          className,
          "transition-all duration-300 ease-out",
          showSuccess &&
            "animate-cart-pop bg-success text-success-foreground shadow-lg shadow-success/30 hover:bg-success/90 dark:bg-success dark:text-success-foreground dark:hover:bg-success/90",
        )}
        disabled={disabled || mutation.isPending}
        onClick={handleClick}
      >
        {showSuccess ? (
          <CircleCheck key="icon-added" aria-hidden="true" className="animate-cart-check-in" />
        ) : (
          <ShoppingCart key="icon-idle" aria-hidden="true" />
        )}
        <span
          key={showSuccess ? "label-added" : mutation.isPending ? "label-pending" : "label-idle"}
          aria-live="polite"
          className="animate-cart-label-in"
        >
          {showSuccess
            ? t("cart.addedToCart")
            : mutation.isPending
              ? t("loading")
              : t("catalog.addToCart")}
        </span>
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
