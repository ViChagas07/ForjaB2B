import type { ProductSummary } from "@/core/domain/catalog";

/**
 * Determina a vendabilidade de um produto para fins EXIBIÇÃO (badge de
 * indisponibilidade). NÃO é autoridade de negócio — o backend valida a venda
 * (status + CA de EPI) de forma definitiva no cart/order. Mantido no frontend
 * apenas para espelhar visualmente o que o backend já garante.
 */
export function isDisplaySellable(product: ProductSummary): boolean {
  if (product.status !== "ACTIVE") {
    return false;
  }
  if (product.is_epi) {
    return product.ca_status === "VALID";
  }
  return true;
}

/** Produto pode ir ao carrinho: vendável e com ao menos o lote mínimo em estoque. */
export function isPurchasable(product: ProductSummary): boolean {
  return isDisplaySellable(product) && product.stock_quantity >= Math.max(1, product.min_order_qty);
}
