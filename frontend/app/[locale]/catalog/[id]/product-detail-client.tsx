"use client";

import { ProductDetailView } from "@/features/catalog";
import { useAddCartItem } from "@/features/cart";

export function ProductDetailClient({ productId }: { productId: string }) {
  const mutation = useAddCartItem();

  function handleAdd(productId: string) {
    mutation.mutate({ product_id: productId, quantity: 1 });
  }

  // Re-render the ProductDetailView's inline "add" button via the mutation state.
  const addingProductId = mutation.isPending ? (mutation.variables?.product_id ?? null) : null;

  return (
    <ProductDetailView productId={productId} onAdd={handleAdd} addingProductId={addingProductId} />
  );
}
