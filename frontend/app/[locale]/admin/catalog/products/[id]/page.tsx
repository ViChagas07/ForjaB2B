import { Suspense } from "react";
import { getTranslations } from "next-intl/server";
import type { Metadata } from "next";

import { SiteHeader } from "@/shared/components/site-header";
import { AdminProductFormClient } from "./admin-product-form-client";

interface AdminProductFormPageProps {
  params: { locale: string; id?: string };
}

export async function generateMetadata({ params }: AdminProductFormPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  const isEdit = Boolean(params.id);
  return { title: t(isEdit ? "admin.catalog.products.form.editTitle" : "admin.catalog.products.form.newTitle") };
}

export default function AdminProductFormPage({ params }: AdminProductFormPageProps) {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <Suspense fallback={null}>
          <AdminProductFormClient productId={params.id ?? null} />
        </Suspense>
      </main>
    </>
  );
}