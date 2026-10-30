import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SiteHeader } from "@/shared/components/site-header";
import { AdminCouponFormClient } from "../admin-coupon-form-client";

interface AdminCouponNewPageProps {
  params: { locale: string };
}

export async function generateMetadata({ params }: AdminCouponNewPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("admin.coupons.form.newTitle") };
}

export default function AdminCouponNewPage() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <AdminCouponFormClient couponId={null} />
      </main>
    </>
  );
}
