import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { OrderDetailView } from "@/features/ordering";
import { SiteHeader } from "@/shared/components/site-header";

interface OrderPageProps {
  params: { id: string };
}

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return { title: t("ordering.reviewTitle") };
}

export default function OrderPage({ params }: OrderPageProps) {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <OrderDetailView orderId={params.id} />
      </main>
    </>
  );
}
