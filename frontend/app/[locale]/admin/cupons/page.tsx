import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SiteHeader } from "@/shared/components/site-header";
import { AdminCouponListClient } from "./admin-coupon-list-client";

interface AdminCouponListPageProps {
  params: { locale: string };
}

export async function generateMetadata({ params }: AdminCouponListPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("admin.coupons.title") };
}

export default function AdminCouponListPage() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <AdminCouponListClient />
      </main>
    </>
  );
}
