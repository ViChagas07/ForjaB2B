import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import type { AccountType } from "@/core/domain/auth";
import { LoginTabs } from "@/features/auth";
import { SiteHeader } from "@/shared/components/site-header";
import { Card, CardContent } from "@/shared/ui/card";

interface LoginPageProps {
  params: { locale: string };
  searchParams?: Record<string, string | string[] | undefined>;
}

export async function generateMetadata({ params }: LoginPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("auth.loginTitle") };
}

function parseAccountType(value: string | string[] | undefined): AccountType {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw === "cnpj" ? "COMPANY" : "PERSON";
}

export default function LoginPage({ searchParams }: LoginPageProps) {
  return (
    <>
      <SiteHeader />
      <main
        id="main"
        className="container flex flex-1 items-start justify-center py-12 sm:items-center"
      >
        <Card className="w-full max-w-md">
          <CardContent className="p-6 sm:p-8">
            <LoginTabs initialType={parseAccountType(searchParams?.tipo)} />
          </CardContent>
        </Card>
      </main>
    </>
  );
}
