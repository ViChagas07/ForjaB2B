import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import type { AccountType } from "@/core/domain/auth";
import { Link } from "@/i18n/navigation";
import { RegisterTabs } from "@/features/auth";
import { SiteHeader } from "@/shared/components/site-header";
import { Card, CardContent } from "@/shared/ui/card";

interface OnboardingPageProps {
  params: { locale: string };
  searchParams?: Record<string, string | string[] | undefined>;
}

export async function generateMetadata({ params }: OnboardingPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("nav.register") };
}

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function parseAccountType(value: string | string[] | undefined): AccountType {
  return first(value) === "cpf" ? "PERSON" : "COMPANY";
}

export default async function OnboardingPage({ searchParams }: OnboardingPageProps) {
  const t = await getTranslations();
  const initialEmail = first(searchParams?.email);
  const initialFullName = first(searchParams?.full_name);

  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex flex-1 justify-center py-12">
        <Card className="w-full max-w-2xl">
          <CardContent className="space-y-6 p-6 sm:p-8">
            <RegisterTabs
              initialType={parseAccountType(searchParams?.tipo)}
              initialEmail={initialEmail}
              initialFullName={initialFullName}
            />
            <p className="text-center text-sm text-muted-foreground">
              {t("onboarding.haveAccount")}{" "}
              <Link
                href="/login"
                className="font-medium text-foreground underline underline-offset-4"
              >
                {t("onboarding.loginLink")}
              </Link>
            </p>
          </CardContent>
        </Card>
      </main>
    </>
  );
}
