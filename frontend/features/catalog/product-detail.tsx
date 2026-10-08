"use client";

import { useLocale, useTranslations } from "next-intl";
import { ArrowLeft, ShoppingCart } from "lucide-react";

import { Link } from "@/i18n/navigation";
import { formatNumber } from "@/shared/lib/money";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { errorMessageKey } from "@/shared/lib/api-error";

import { useProduct } from "./hooks";
import { isDisplaySellable } from "./availability";
import { CatalogPrice } from "./catalog-price";
import { AvailabilityBadge, CaStatusBadge, EpiBadge } from "./product-badges";

interface ProductDetailViewProps {
  productId: string;
  onAdd?: (productId: string) => void;
  addingProductId?: string | null;
}

export function ProductDetailView({ productId, onAdd, addingProductId }: ProductDetailViewProps) {
  const t = useTranslations();
  const locale = useLocale();
  const isAuthenticated = useAuthStore((s) => s.status === "authenticated");
  const query = useProduct(productId);

  if (query.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("catalog.loadError")}</AlertTitle>
        <AlertDescription>{t(errorMessageKey(query.error))}</AlertDescription>
      </Alert>
    );
  }

  const product = query.data;
  if (!product) {
    return (
      <Alert variant="warning">
        <AlertDescription>{t("catalog.noResults")}</AlertDescription>
      </Alert>
    );
  }

  const sellable = isDisplaySellable(product);

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild>
        <Link href="/catalog">
          <ArrowLeft aria-hidden="true" />
          {t("catalog.backToCatalog")}
        </Link>
      </Button>

      <Card>
        <CardHeader>
          <CardTitle className="text-2xl tracking-tight">{product.name}</CardTitle>
          <div className="flex flex-wrap gap-1.5">
            <EpiBadge isEpi={product.is_epi} />
            <CaStatusBadge status={product.ca_status} />
            <AvailabilityBadge isSellable={sellable} />
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <CatalogPrice
              amount={product.base_unit_price}
              currency={product.currency}
              className="text-3xl font-bold"
            />
            {onAdd ? (
              <Button
                disabled={!isAuthenticated || !sellable || addingProductId === product.id}
                onClick={() => onAdd(product.id)}
              >
                <ShoppingCart aria-hidden="true" />
                {addingProductId === product.id ? t("loading") : t("catalog.addToCart")}
              </Button>
            ) : null}
          </div>

          {product.description ? (
            <div>
              <h2 className="mb-2 font-medium">{t("catalog.description")}</h2>
              <p className="text-sm text-muted-foreground">{product.description}</p>
            </div>
          ) : null}

          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-sm text-muted-foreground">{t("catalog.sku")}</dt>
              <dd className="font-mono font-medium">{product.sku}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">{t("catalog.category")}</dt>
              <dd className="font-medium">{product.category.name}</dd>
            </div>
            {product.brand ? (
              <div>
                <dt className="text-sm text-muted-foreground">{t("catalog.brand")}</dt>
                <dd className="font-medium">{product.brand.name}</dd>
              </div>
            ) : null}
            {product.unit_of_measure ? (
              <div>
                <dt className="text-sm text-muted-foreground">{t("catalog.unit")}</dt>
                <dd className="font-medium">{product.unit_of_measure}</dd>
              </div>
            ) : null}
            <div>
              <dt className="text-sm text-muted-foreground">{t("catalog.minOrderQty")}</dt>
              <dd className="font-medium">{product.min_order_qty}</dd>
            </div>
            {product.weight_kg != null ? (
              <div>
                <dt className="text-sm text-muted-foreground">{t("catalog.weight")}</dt>
                <dd className="font-medium">
                  {t("catalog.weightKg", {
                    weight: formatNumber(Number(product.weight_kg), locale),
                  })}
                </dd>
              </div>
            ) : null}
            {product.ca_number ? (
              <div>
                <dt className="text-sm text-muted-foreground">{t("catalog.caNumber")}</dt>
                <dd className="font-medium">{product.ca_number}</dd>
              </div>
            ) : null}
            {product.ncm ? (
              <div>
                <dt className="text-sm text-muted-foreground">{t("catalog.ncm")}</dt>
                <dd className="font-mono font-medium">{product.ncm}</dd>
              </div>
            ) : null}
          </dl>

          {product.attributes && Object.keys(product.attributes).length > 0 ? (
            <div>
              <h2 className="mb-2 font-medium">{t("catalog.attributes")}</h2>
              <dl className="grid gap-2 sm:grid-cols-2">
                {Object.entries(product.attributes).map(([key, value]) => (
                  <div key={key} className="flex gap-2 text-sm">
                    <dt className="text-muted-foreground">{key}:</dt>
                    <dd className="font-medium">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
