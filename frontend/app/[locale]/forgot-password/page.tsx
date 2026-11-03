import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { ForgotPasswordFlow } from "@/features/auth/forgot-password-flow";
import { SiteHeader } from "@/shared/components/site-header";
import { Card, CardContent } from "@/shared/ui/card";

interface ForgotPasswordPageProps {
  params: { locale: string };
}

export async function generateMetadata({ params }: ForgotPasswordPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("forgotPassword.title") };
}

export default function ForgotPasswordPage() {
  if (process.env.NEXT_PUBLIC_PASSWORD_RECOVERY_ENABLED !== "true") {
    notFound();
  }
  const nonce = headers().get("x-nonce") ?? undefined;
  const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

  return (
    <>
      <SiteHeader />
      <main
        id="main"
        className="container flex flex-1 items-start justify-center py-12 sm:items-center"
      >
        <Card className="w-full max-w-lg">
          <CardContent className="p-6 sm:p-8">
            <ForgotPasswordFlow siteKey={siteKey} nonce={nonce} />
          </CardContent>
        </Card>
      </main>
    </>
  );
}
