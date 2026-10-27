import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";

import { BrandLogo } from "./brand-logo";

const columnTitleClass = "text-[11px] font-semibold uppercase tracking-[0.2em] text-white/60";

const footerLinkClass = "text-sm text-white/65 transition-colors hover:text-primary";

export async function SiteFooter() {
  const t = await getTranslations();
  const year = new Date().getFullYear();

  return (
    <footer className="surface-ink mt-auto border-t border-white/10">
      <div className="container grid gap-12 py-16 lg:grid-cols-[1.5fr_1fr_1fr_1fr]">
        <div className="max-w-sm space-y-5">
          <BrandLogo />
          <p className="text-sm leading-relaxed text-white/55">{t("footer.tagline")}</p>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] font-medium text-white/65">
            <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-primary" />
            {t("footer.note")}
          </div>
        </div>

        <div className="space-y-4">
          <h2 className={columnTitleClass}>{t("footer.navTitle")}</h2>
          <ul className="space-y-2.5">
            <li>
              <Link href="/catalog" className={footerLinkClass}>
                {t("catalog.title")}
              </Link>
            </li>
            <li>
              <Link href="/#solucoes" className={footerLinkClass}>
                {t("footer.categories")}
              </Link>
            </li>
            <li>
              <Link href="/#a-forja" className={footerLinkClass}>
                {t("nav.about")}
              </Link>
            </li>
            <li>
              <Link href="/privacy" className={footerLinkClass}>
                {t("footer.privacy")}
              </Link>
            </li>
          </ul>
        </div>

        <div className="space-y-4">
          <h2 className={columnTitleClass}>{t("footer.businessTitle")}</h2>
          <ul className="space-y-2.5">
            <li>
              <Link href="/onboarding" className={footerLinkClass}>
                {t("nav.register")}
              </Link>
            </li>
            <li>
              <Link href="/login" className={footerLinkClass}>
                {t("nav.login")}
              </Link>
            </li>
            <li>
              <Link href="/dashboard" className={footerLinkClass}>
                {t("nav.dashboard")}
              </Link>
            </li>
          </ul>
        </div>

        <div className="space-y-4">
          <h2 className={columnTitleClass}>{t("footer.accountTitle")}</h2>
          <ul className="space-y-2.5">
            <li>
              <Link href="/cart" className={footerLinkClass}>
                {t("nav.cart")}
              </Link>
            </li>
            <li>
              <Link href="/dashboard" className={footerLinkClass}>
                {t("footer.orders")}
              </Link>
            </li>
            <li>
              <Link href="/dashboard" className={footerLinkClass}>
                {t("footer.credit")}
              </Link>
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-white/10">
        <div className="container flex flex-col gap-3 py-6 text-xs text-white/60 sm:flex-row sm:items-center sm:justify-between">
          <p>{t("footer.copyright", { year })}</p>
          <p>{t("footer.madeIn")}</p>
        </div>
      </div>
    </footer>
  );
}
