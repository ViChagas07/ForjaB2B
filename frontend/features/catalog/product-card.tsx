"use client";

import { useTranslations } from "next-intl";
import { ShoppingCart } from "lucide-react";

import { Link } from "@/i18n/navigation";
import type { ProductSummary } from "@/core/domain/catalog";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/shared/ui/card";

import { isDisplaySellable } from "./availability";
import { CatalogPrice } from "./catalog-price";
import { AvailabilityBadge, CaStatusBadge, EpiBadge } from "./product-badges";

interface ProductCardProps {
  product: ProductSummary;
  onAdd?: (productId: string) => void;
  addingProductId?: string | null;
}

export function ProductCard({ product, onAdd, addingProductId }: ProductCardProps) {
  const t = useTranslations();
  const isAuthenticated = useAuthStore((s) => s.status === "authenticated");
  const sellable = isDisplaySellable(product);

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base leading-snug">
            <Link href={`/catalog/${product.id}`} className="hover:underline">
              {product.name}
            </Link>
          </CardTitle>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <EpiBadge isEpi={product.is_epi} />
          <CaStatusBadge status={product.ca_status} />
          <AvailabilityBadge isSellable={sellable} />
        </div>
      </CardHeader>
      <CardContent className="flex-1 space-y-1.5 text-sm">
        <p className="text-muted-foreground">
          {t("catalog.sku")}: <span className="font-mono">{product.sku}</span>
        </p>
        {product.brand ? (
          <p className="text-muted-foreground">
            {t("catalog.brand")}: {product.brand.name}
          </p>
        ) : null}
        <p className="text-muted-foreground">
          {t("catalog.minOrderQty")}: {product.min_order_qty}
        </p>
      </CardContent>
      <CardFooter className="flex flex-col items-stretch gap-3">
        <CatalogPrice
          amount={product.base_unit_price}
          currency={product.currency}
          className="text-lg font-semibold"
        />
        {onAdd ? (
          <Button
            size="sm"
            className="w-full"
            disabled={!isAuthenticated || !sellable || addingProductId === product.id}
            onClick={() => onAdd(product.id)}
          >
            <ShoppingCart aria-hidden="true" />
            {addingProductId === product.id ? t("loading") : t("catalog.addToCart")}
          </Button>
        ) : null}
      </CardFooter>
    </Card>
  );
}
