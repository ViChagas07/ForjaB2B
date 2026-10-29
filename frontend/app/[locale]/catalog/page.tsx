import type { Metadata } from "next";
import { Suspense } from "react";
import { dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { getLocale, getTranslations } from "next-intl/server";

import { CatalogBrowser } from "@/features/catalog";
import { CatalogLoadingSkeleton } from "@/features/catalog/catalog-skeleton";
import {
  parseCatalogSearchParams,
  type CatalogSearchParamsInput,
} from "@/features/catalog/search-params";
import { prefetchCatalogPage } from "@/features/catalog/server-prefetch";
import { SiteFooter } from "@/shared/components/site-footer";
import { SiteHeader } from "@/shared/components/site-header";
import { getQueryClient } from "@/shared/lib/query-client";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return { title: t("catalog.title") };
}

interface CatalogPageProps {
  searchParams: CatalogSearchParamsInput;
}

export default async function CatalogPage({ searchParams }: CatalogPageProps) {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-12">
        <Suspense fallback={<CatalogLoadingSkeleton />}>
          <CatalogContent searchParams={searchParams} />
        </Suspense>
      </main>
      <SiteFooter />
    </>
  );
}

async function CatalogContent({ searchParams }: CatalogPageProps) {
  const locale = await getLocale();
  const state = parseCatalogSearchParams(searchParams);
  const queryClient = getQueryClient();
  await prefetchCatalogPage(queryClient, locale, state);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <CatalogBrowser />
    </HydrationBoundary>
  );
}
