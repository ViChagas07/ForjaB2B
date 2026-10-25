import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SiteFooter } from "@/shared/components/site-footer";
import { SiteHeader } from "@/shared/components/site-header";
import { CheckoutClient } from "./checkout-client";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return { title: t("ordering.reviewTitle") };
}

export default function CheckoutPage() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-12">
        <CheckoutClient />
      </main>
      <SiteFooter />
    </>
  );
}
