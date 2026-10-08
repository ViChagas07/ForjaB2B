import type { Metadata } from "next";
import * as React from "react";
import { getTranslations } from "next-intl/server";

import { CatalogBrowser } from "@/features/catalog";
import { SiteHeader } from "@/shared/components/site-header";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return { title: t("catalog.title") };
}

export default function CatalogPage() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <React.Suspense fallback={null}>
          <CatalogBrowser />
        </React.Suspense>
      </main>
    </>
  );
}
