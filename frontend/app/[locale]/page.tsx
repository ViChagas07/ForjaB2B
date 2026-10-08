import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { SiteHeader } from "@/shared/components/site-header";
import { Button } from "@/shared/ui/button";

export default async function HomePage() {
  const t = await getTranslations();

  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex flex-1 flex-col justify-center py-16">
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 text-center">
          <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            {t("homeTitle")}
          </h1>
          <p className="max-w-xl text-lg text-muted-foreground">{t("homeDescription")}</p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button asChild>
              <Link href="/login">{t("homeLogin")}</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/onboarding">{t("homeSignUp")}</Link>
            </Button>
          </div>
        </div>
      </main>
      <footer className="border-t py-6">
        <div className="container text-center text-sm text-muted-foreground">
          © {new Date().getFullYear()} {t("appName")}
        </div>
      </footer>
    </>
  );
}
