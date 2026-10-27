"use client";

import { useTranslations } from "next-intl";

import type { components } from "@/core/domain/api-schema";
import { CaStatusBadge, CatalogPrice } from "@/features/catalog";
import { cn } from "@/shared/lib/utils";
import { ProductImage } from "@/shared/components/product-image";

type SearchProduct = components["schemas"]["SearchProductOut-Output"];

interface ProductPreviewListProps {
  products: SearchProduct[];
  /** Termo da resposta (para o título "Resultados populares para “q”"). */
  query: string;
  /** Id do listbox (pai) para gerar ids estáveis das opções. */
  listboxId: string;
  /** Índice absoluto da primeira opção desta lista na navegação plana. */
  baseIndex: number;
  activeIndex: number | null;
  onActiveIndexChange: (index: number) => void;
  onProductSelect: (product: SearchProduct) => void;
}

/**
 * Coluna direita do dropdown: título com o termo da resposta e até 6 produtos
 * (imagem, nome, SKU, preço por empresa, selo de CA válido e pedido mínimo).
 * Cada opção navega para a página do produto (/catalog/<id>).
 */
export function ProductPreviewList({
  products,
  query,
  listboxId,
  baseIndex,
  activeIndex,
  onActiveIndexChange,
  onProductSelect,
}: ProductPreviewListProps) {
  const t = useTranslations();
  if (products.length === 0) {
    return null;
  }

  return (
    <li
      role="group"
      aria-label={t("search.popularResultsFor", { q: query })}
      className="min-w-0 border-t border-border/60 md:col-start-2 md:row-start-1 md:border-t-0"
    >
      <p className="border-b border-border/60 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {t("search.popularResultsFor", { q: query })}
      </p>
      <ul className="divide-y divide-border/60">
        {products.map((product, offset) => {
          const absoluteIndex = baseIndex + offset;
          const optionId = `${listboxId}-opt-${absoluteIndex}`;
          return (
            <li
              key={product.id}
              role="option"
              id={optionId}
              aria-selected={activeIndex === absoluteIndex}
              onMouseDown={(event) => event.preventDefault()}
              onMouseMove={() => onActiveIndexChange(absoluteIndex)}
              onClick={() => onProductSelect(product)}
              className={cn(
                "flex cursor-pointer items-start gap-3 px-4 py-3",
                activeIndex === absoluteIndex
                  ? "bg-accent text-accent-foreground"
                  : "hover:bg-muted/60",
              )}
            >
              <ProductImage
                src={product.image_url}
                alt={product.image_alt || product.name}
                width={64}
                height={64}
                className="h-16 w-16 shrink-0 rounded-xl border border-border bg-secondary/50"
              />
              <div className="min-w-0 flex-1">
                <p className="line-clamp-2 text-sm font-medium leading-snug">{product.name}</p>
                <p className="font-mono text-[11px] text-muted-foreground">
                  {t("catalog.sku")}: {product.sku}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                  <CatalogPrice
                    amount={product.base_unit_price}
                    currency={product.currency}
                    priceOnRequest={product.price_on_request}
                    className="text-sm font-bold tracking-tight"
                  />
                  {product.ca_status === "VALID" ? <CaStatusBadge status="VALID" /> : null}
                  {product.min_order_qty > 1 ? (
                    <span className="text-[11px] text-muted-foreground">
                      {t("cart.minQuantity", { qty: product.min_order_qty })}
                    </span>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </li>
  );
}
