import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SiteFooter } from "@/shared/components/site-footer";
import { SiteHeader } from "@/shared/components/site-header";
import { CheckoutClient } from "./checkout-client";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return { title: t("ordering.reviewTitle") };
}

interface CheckoutPageProps {
  searchParams: { items?: string | string[] };
}

export default function CheckoutPage({ searchParams }: CheckoutPageProps) {
  const rawItems = Array.isArray(searchParams.items) ? searchParams.items[0] : searchParams.items;
  const parsedItems = rawItems
    ? rawItems
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
    : null;
  const selectedProductIds = parsedItems && parsedItems.length > 0 ? parsedItems : null;

  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-12">
        <CheckoutClient selectedProductIds={selectedProductIds} />
      </main>
      <SiteFooter />
    </>
  );
}
