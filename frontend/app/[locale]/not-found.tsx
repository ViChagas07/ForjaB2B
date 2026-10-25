import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { Button } from "@/shared/ui/button";

export default async function NotFound() {
  const t = await getTranslations();

  return (
    <main
      id="main"
      className="container flex flex-1 flex-col items-center justify-center gap-4 py-24 text-center"
    >
      <p className="text-8xl font-black tracking-tighter text-forge-700 dark:text-forge-300">404</p>
      <h1 className="text-2xl font-black tracking-tight">{t("notFoundTitle")}</h1>
      <p className="max-w-md text-sm text-muted-foreground">{t("notFoundDescription")}</p>
      <Button asChild className="mt-2 rounded-xl">
        <Link href="/">{t("notFoundBackHome")}</Link>
      </Button>
    </main>
  );
}
