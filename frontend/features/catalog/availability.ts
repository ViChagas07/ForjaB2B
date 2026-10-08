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
