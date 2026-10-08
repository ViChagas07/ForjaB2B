import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { CartView } from "@/features/cart";
import { SiteHeader } from "@/shared/components/site-header";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return { title: t("cart.title") };
}

export default function CartPage() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <CartView />
      </main>
    </>
  );
}
