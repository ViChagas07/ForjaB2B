import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { LoginForm } from "@/features/auth";
import { SiteHeader } from "@/shared/components/site-header";
import { Card, CardContent, CardDescription, CardHeader } from "@/shared/ui/card";

interface LoginPageProps {
  params: { locale: string };
}

export async function generateMetadata({ params }: LoginPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("auth.loginTitle") };
}

export default async function LoginPage() {
  const t = await getTranslations();

  return (
    <>
      <SiteHeader />
      <main
        id="main"
        className="container flex flex-1 items-start justify-center py-12 sm:items-center"
      >
        <Card className="w-full max-w-md">
          <CardHeader>
            <h1 className="text-2xl font-semibold tracking-tight">{t("auth.loginTitle")}</h1>
            <CardDescription>{t("auth.loginSubtitle")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <LoginForm />
            <p className="text-center text-sm text-muted-foreground">
              {t("auth.loginNoAccount")}{" "}
              <Link
                href="/onboarding"
                className="font-medium text-foreground underline underline-offset-4"
              >
                {t("auth.loginCreateAccount")}
              </Link>
            </p>
          </CardContent>
        </Card>
      </main>
    </>
  );
}
