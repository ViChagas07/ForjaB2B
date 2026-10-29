"use client";

import { ArrowUpRight } from "lucide-react";
import { useTranslations } from "next-intl";

import type { ProductSummary } from "@/core/domain/catalog";
import { AddToCartButton, BuyNowButton } from "@/features/cart";
import { Link } from "@/i18n/navigation";
import { displayCategoryName } from "@/shared/lib/category-display";
import { cn } from "@/shared/lib/utils";
import { ProductImage } from "@/shared/components/product-image";

import { isPurchasable } from "./availability";
import { CatalogPrice } from "./catalog-price";
import { AvailabilityBadge, CaStatusBadge, EpiBadge } from "./product-badges";

interface ProductCardProps {
  product: ProductSummary;
  className?: string;
}

/**
 * Cartão de produto do catálogo. O clique na imagem/nome abre o detalhe; a
 * compra é feita pelos botões de compra/carrinho, que exigem sessão
 * autenticada e respeitam o estoque disponível.
 */
export function ProductCard({ product, className }: ProductCardProps) {
  const t = useTranslations();
  const purchasable = isPurchasable(product);
  const hasStock = (product.stock_quantity ?? 0) > 0;

  return (
    <article
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl border border-border bg-card transition-all duration-300 hover:-translate-y-1 hover:border-primary/40 hover:shadow-[0_24px_50px_-32px_rgba(10,10,10,0.45)]",
        className,
      )}
    >
      <Link
        href={`/catalog/${product.id}`}
        className="relative block aspect-square overflow-hidden bg-secondary/70"
      >
        <ProductImage
          src={product.image_url}
          alt={product.image_alt}
          className="h-full w-full transition-transform duration-500 group-hover:scale-[1.04]"
        />
        <div className="absolute start-3 top-3 flex flex-wrap gap-1.5">
          <EpiBadge isEpi={product.is_epi} />
          <CaStatusBadge status={product.ca_status} />
          <AvailabilityBadge isSellable={purchasable} />
        </div>
        <span className="absolute end-3 top-3 flex h-8 w-8 items-center justify-center rounded-lg bg-white/90 text-foreground opacity-0 shadow-sm transition-opacity duration-300 group-hover:opacity-100">
          <ArrowUpRight aria-hidden="true" className="h-4 w-4 rtl:-scale-x-100" />
        </span>
      </Link>

      <div className="flex flex-1 flex-col gap-3 p-5">
        <div className="flex items-center justify-between gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          <span className="truncate">{displayCategoryName(product.category.name)}</span>
          {product.brand ? <span className="shrink-0">{product.brand.name}</span> : null}
        </div>

        <h3 className="line-clamp-2 text-base font-semibold leading-snug">
          <Link
            href={`/catalog/${product.id}`}
            className="transition-colors hover:text-forge-700 dark:hover:text-forge-300"
          >
            {product.name}
          </Link>
        </h3>

        <p className="font-mono text-[11px] text-muted-foreground">
          {t("catalog.sku")}: {product.sku}
        </p>

        <div className="mt-auto space-y-3 pt-1">
          <div>
            <CatalogPrice
              amount={product.base_unit_price}
              currency={product.currency}
              priceOnRequest={product.price_on_request}
              className="text-xl font-bold tracking-tight"
            />
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              {t("cart.minQuantity", { qty: product.min_order_qty })}
            </p>
            <p
              className={cn(
                "mt-1 text-[11px] font-semibold",
                hasStock ? "text-success" : "text-destructive",
              )}
            >
              {hasStock
                ? t("catalog.inStock", { count: product.stock_quantity })
                : t("catalog.outOfStock")}
            </p>
          </div>

          <div className="grid gap-2">
            <BuyNowButton
              productId={product.id}
              minQuantity={product.min_order_qty}
              disabled={!purchasable}
              className="h-10 w-full rounded-xl"
            />
            <AddToCartButton
              productId={product.id}
              minQuantity={product.min_order_qty}
              disabled={!purchasable}
              className="h-10 w-full rounded-xl"
            />
          </div>
        </div>
      </div>
    </article>
  );
}
