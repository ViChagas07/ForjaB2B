import type { Metadata } from "next";
import { Suspense } from "react";
import { dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { getLocale, getTranslations } from "next-intl/server";

import { prefetchProductDetail } from "@/features/catalog/server-prefetch";
import { SiteFooter } from "@/shared/components/site-footer";
import { SiteHeader } from "@/shared/components/site-header";
import { getQueryClient } from "@/shared/lib/query-client";
import { Skeleton } from "@/shared/ui/skeleton";

import { ProductDetailClient } from "./product-detail-client";

interface ProductDetailPageProps {
  params: { id: string };
}

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return { title: t("catalog.details") };
}

export default async function ProductDetailPage({ params }: ProductDetailPageProps) {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-12">
        <Suspense fallback={<ProductDetailSkeleton />}>
          <ProductDetailContent productId={params.id} />
        </Suspense>
      </main>
      <SiteFooter />
    </>
  );
}

async function ProductDetailContent({ productId }: { productId: string }) {
  const locale = await getLocale();
  const queryClient = getQueryClient();
  await prefetchProductDetail(queryClient, locale, productId);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <ProductDetailClient productId={productId} />
    </HydrationBoundary>
  );
}

function ProductDetailSkeleton() {
  return (
    <div aria-busy="true" className="grid gap-8 lg:grid-cols-2">
      <Skeleton className="aspect-square w-full rounded-3xl" />
      <div className="space-y-4">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-10 w-3/4" />
        <Skeleton className="h-40 w-full rounded-2xl" />
        <Skeleton className="h-24 w-full rounded-2xl" />
      </div>
    </div>
  );
}
