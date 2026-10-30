import { getTranslations } from "next-intl/server";

import { BrandLogo } from "./brand-logo";
import { SiteFooterLinks } from "./site-footer-links";

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

        <SiteFooterLinks />
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
