import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { RegisterCompanyForm } from "@/features/companies";
import { SiteHeader } from "@/shared/components/site-header";
import { Card, CardContent, CardDescription, CardHeader } from "@/shared/ui/card";

interface OnboardingPageProps {
  params: { locale: string };
}

export async function generateMetadata({ params }: OnboardingPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("onboarding.title") };
}

export default async function OnboardingPage() {
  const t = await getTranslations();

  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex flex-1 justify-center py-12">
        <Card className="w-full max-w-2xl">
          <CardHeader>
            <h1 className="text-2xl font-semibold tracking-tight">{t("onboarding.title")}</h1>
            <CardDescription>{t("onboarding.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <RegisterCompanyForm />
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
