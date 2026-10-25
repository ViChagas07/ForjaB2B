import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SiteHeader } from "@/shared/components/site-header";
import { AdminProductListClient } from "./admin-product-list-client";

interface AdminProductListPageProps {
  params: { locale: string };
}

export async function generateMetadata({ params }: AdminProductListPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("admin.catalog.products.title") };
}

export default function AdminProductListPage() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <AdminProductListClient />
      </main>
    </>
  );
}
