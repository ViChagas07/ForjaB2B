import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { DashboardClient } from "./dashboard-client";
import { SiteHeader } from "@/shared/components/site-header";

interface DashboardPageProps {
  params: { locale: string };
}

export async function generateMetadata({ params }: DashboardPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("dashboard.title") };
}

export default function DashboardPage() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <DashboardClient />
      </main>
    </>
  );
}
