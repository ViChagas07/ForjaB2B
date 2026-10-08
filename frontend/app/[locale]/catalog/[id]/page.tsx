import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SiteHeader } from "@/shared/components/site-header";
import { ProductDetailClient } from "./product-detail-client";

interface ProductDetailPageProps {
  params: { id: string };
}

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return { title: t("catalog.details") };
}

export default function ProductDetailPage({ params }: ProductDetailPageProps) {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <ProductDetailClient productId={params.id} />
      </main>
    </>
  );
}
