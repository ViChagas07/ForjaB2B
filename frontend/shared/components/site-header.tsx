import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";

import { BrandLogo } from "./brand-logo";
import { HeaderActions } from "./header-actions";
import { HeaderSearch } from "./header-search";

const navLinkClass =
  "rounded-lg px-3 py-2 text-sm font-medium text-white/65 transition-colors hover:bg-white/10 hover:text-white";

export async function SiteHeader() {
  const t = await getTranslations();

  return (
    <header className="sticky top-0 z-50 w-screen max-w-none border-b border-white/10 bg-ink/95 text-white backdrop-blur supports-[backdrop-filter]:bg-ink/90">
      <div className="flex h-[72px] w-full items-center gap-4 px-0 lg:gap-7">
        <BrandLogo />

        <nav aria-label={t("nav.primary")} className="hidden items-center gap-0.5 lg:flex">
          <Link href="/catalog" className={navLinkClass}>
            {t("catalog.title")}
          </Link>
          <Link href="/#solucoes" className={navLinkClass}>
            {t("nav.solutions")}
          </Link>
          <Link href="/#a-forja" className={navLinkClass}>
            {t("nav.about")}
          </Link>
        </nav>

        <div className="ms-auto hidden max-w-sm flex-1 md:flex xl:absolute xl:inset-x-0 xl:inset-y-0 xl:mx-auto xl:w-80 xl:max-w-none xl:flex-none xl:items-center">
          <HeaderSearch className="w-full" />
        </div>
        <div className="ms-auto">
          <HeaderActions />
        </div>
      </div>

      <div className="border-t border-white/10 px-0 py-2.5 md:hidden">
        <HeaderSearch />
      </div>
    </header>
  );
}
