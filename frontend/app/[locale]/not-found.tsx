import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { Button } from "@/shared/ui/button";

export default async function NotFound() {
  const t = await getTranslations();

  return (
    <main className="container flex flex-1 flex-col items-center justify-center gap-4 py-24 text-center">
      <p className="text-7xl font-bold text-primary">404</p>
      <h1 className="text-2xl font-semibold">{t("notFoundTitle")}</h1>
      <p className="text-muted-foreground">{t("notFoundDescription")}</p>
      <Button asChild>
        <Link href="/">{t("notFoundBackHome")}</Link>
      </Button>
    </main>
  );
}
