"use client";

import * as React from "react";
import { LockKeyhole, ShoppingCart } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";

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
 *
 * O carrinho é tenant-scoped: visitantes podem navegar pelo catálogo, mas ao
 * tentar guardar um item recebem o convite para entrar/cadastrar a empresa.
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
  const status = useAuthStore((s) => s.status);
  const mutation = useAddCartItem();
  const [gateOpen, setGateOpen] = React.useState(false);

  const isAuthenticated = status === "authenticated";

  function handleClick() {
    if (!isAuthenticated) {
      setGateOpen(true);
      return;
    }
    mutation.mutate({ product_id: productId, quantity: minQuantity });
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

      <Dialog open={gateOpen} onOpenChange={setGateOpen}>
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader className="space-y-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent text-accent-foreground">
              <LockKeyhole aria-hidden="true" className="h-5 w-5" />
            </span>
            <DialogTitle className="text-xl">{t("authGate.title")}</DialogTitle>
            <DialogDescription>{t("authGate.description")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 pt-2">
            <Button asChild size="lg" className="rounded-xl">
              <Link href="/login">{t("nav.login")}</Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="rounded-xl">
              <Link href="/onboarding">{t("nav.register")}</Link>
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
