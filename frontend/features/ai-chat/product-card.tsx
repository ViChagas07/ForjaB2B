"use client";

import { ShoppingCart } from "lucide-react";
import { useTranslations } from "next-intl";

import { CaStatusBadge, CatalogPrice } from "@/features/catalog";
import { useAddCartItem } from "@/features/cart";
import type { ChatProductCard } from "@/infrastructure/http";
import { Link, useRouter } from "@/i18n/navigation";
import { ProductImage } from "@/shared/components/product-image";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Button } from "@/shared/ui/button";

/**
 * Cartão de produto do chat. Imagem/nome/SKU/preço/link vêm do BACKEND
 * (montados a partir do Postgres); o texto do assistente NUNCA vira link.
 * Visitante vê "sob consulta" (price_on_request) e o botão de carrinho leva
 * ao login; logado usa a mutation existente do carrinho.
 */
export function ChatProductCardView({ card }: { card: ChatProductCard }) {
  const t = useTranslations();
  const router = useRouter();
  const status = useAuthStore((s) => s.status);
  const addItem = useAddCartItem();
  const isAuthenticated = status === "authenticated";

  function handleAddToCart() {
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    addItem.mutate({ product_id: card.product_id, quantity: card.min_order_qty });
  }

  return (
    <li className="flex gap-3 rounded-xl border border-border/70 bg-card/80 p-3">
      <ProductImage
        src={card.image_url}
        alt={card.image_alt || card.name}
        width={64}
        height={64}
        className="h-16 w-16 shrink-0 rounded-lg border border-border bg-secondary/40"
      />
      <div className="min-w-0 flex-1 space-y-1">
        <p className="line-clamp-2 text-sm font-medium leading-snug">{card.name}</p>
        <p className="font-mono text-[11px] text-muted-foreground">
          {t("catalog.sku")}: {card.sku}
        </p>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <CatalogPrice
            amount={card.price}
            currency={card.currency}
            priceOnRequest={card.price_on_request}
            className="text-sm font-bold tracking-tight"
          />
          {card.ca_status === "VALID" ? <CaStatusBadge status="VALID" /> : null}
        </div>
        <div className="flex flex-wrap gap-2 pt-1">
          <Button asChild size="sm" variant="outline" className="h-7 px-2 text-xs">
            <Link href={`/catalog/${card.product_id}`}>{t("aiChat.viewProduct")}</Link>
          </Button>
          <Button
            size="sm"
            variant="ink"
            className="h-7 gap-1 px-2 text-xs"
            onClick={handleAddToCart}
            disabled={addItem.isPending}
          >
            <ShoppingCart aria-hidden="true" className="h-3 w-3" />
            {t("aiChat.addToCart")}
          </Button>
        </div>
      </div>
    </li>
  );
}
