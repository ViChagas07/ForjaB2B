"use client";

import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { useAuthStore } from "@/shared/stores/auth-store";

const columnTitleClass = "text-[11px] font-semibold uppercase tracking-[0.2em] text-white/60";

const footerLinkClass = "text-sm text-white/65 transition-colors hover:text-primary";

/**
 * Colunas de links do rodape (precisam do estado de auth para o layout mobile).
 *
 * Mobile: Navegar e Para Empresas ficam lado a lado; Sua Conta fica na linha
 * seguinte. Depois do login, Para Empresas some e Sua Conta sobe para a
 * direita de Navegar, ganhando o link Painel. No desktop o grid de 4 colunas
 * do SiteFooter continua valendo via `lg:contents`.
 */
export function SiteFooterLinks() {
  const t = useTranslations();
  const status = useAuthStore((state) => state.status);
  const session = useAuthStore((state) => state.session);
  const isAuthenticated = status === "authenticated" && Boolean(session);

  return (
    <div className="grid grid-cols-2 gap-8 lg:contents">
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

      <div className={`space-y-4 ${isAuthenticated ? "hidden lg:block" : ""}`}>
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
          {isAuthenticated ? (
            <li>
              <Link href="/dashboard" className={footerLinkClass}>
                {t("nav.dashboard")}
              </Link>
            </li>
          ) : null}
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
  );
}
