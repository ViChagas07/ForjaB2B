import { Suspense } from "react";
import { getTranslations } from "next-intl/server";
import type { Metadata } from "next";

import { SiteHeader } from "@/shared/components/site-header";
import { AdminProductFormClient } from "../[id]/admin-product-form-client";

interface AdminProductNewPageProps {
  params: { locale: string };
}

export async function generateMetadata({ params }: AdminProductNewPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("admin.catalog.products.form.newTitle") };
}

export default function AdminProductNewPage() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <Suspense fallback={null}>
          <AdminProductFormClient productId={null} />
        </Suspense>
      </main>
    </>
  );
}