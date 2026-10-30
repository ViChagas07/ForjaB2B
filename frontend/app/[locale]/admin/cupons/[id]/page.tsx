import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SiteHeader } from "@/shared/components/site-header";
import { AdminCouponFormClient } from "../admin-coupon-form-client";

interface AdminCouponDetailPageProps {
  params: { locale: string; id: string };
}

export async function generateMetadata({ params }: AdminCouponDetailPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("admin.coupons.form.editTitle") };
}

export default function AdminCouponDetailPage({ params }: AdminCouponDetailPageProps) {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <AdminCouponFormClient couponId={params.id} />
      </main>
    </>
  );
}
