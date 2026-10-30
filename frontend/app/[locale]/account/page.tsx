import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SiteFooter } from "@/shared/components/site-footer";
import { SiteHeader } from "@/shared/components/site-header";
import { AccountClient } from "./account-client";

interface AccountPageProps {
  params: { locale: string };
}

export async function generateMetadata({ params }: AccountPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("account.title") };
}

export default function AccountPage() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-10">
        <AccountClient />
      </main>
      <SiteFooter />
    </>
  );
}
