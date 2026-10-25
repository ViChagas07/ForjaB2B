"use client";

import { ProductDetailView } from "@/features/catalog";

interface ProductDetailClientProps {
  productId: string;
}

export function ProductDetailClient({ productId }: ProductDetailClientProps) {
  return <ProductDetailView productId={productId} />;
}
