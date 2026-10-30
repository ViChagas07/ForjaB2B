import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SiteFooter } from "@/shared/components/site-footer";
import { SiteHeader } from "@/shared/components/site-header";
import { SettingsClient } from "./settings-client";

interface SettingsPageProps {
  params: { locale: string };
}

export async function generateMetadata({ params }: SettingsPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("settings.title") };
}

export default function SettingsPage() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <SettingsClient />
      </main>
      <SiteFooter />
    </>
  );
}
