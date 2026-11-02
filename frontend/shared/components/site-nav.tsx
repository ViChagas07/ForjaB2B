"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";

const navLinkClass =
  "rounded-lg px-3 py-2 text-sm font-medium text-white/65 transition-colors hover:bg-white/10 hover:text-white";
const activeNavLinkClass = "bg-white/10 text-white";

const SECTION_IDS = ["solucoes", "a-forja"] as const;
type SectionId = (typeof SECTION_IDS)[number];

// Altura do header fixo (72px) mais uma folga para o topo da seção.
const HEADER_OFFSET = 88;

/**
 * Navegação principal com estado ativo: "Catálogo" fica destacado enquanto a
 * rota for de catálogo e "Soluções"/"A Forja" ficam destacados apenas enquanto
 * a respectiva seção da home estiver sob o header (scrollspy).
 */
export function SiteNav() {
  const t = useTranslations();
  const pathname = usePathname();
  const [activeSection, setActiveSection] = React.useState<SectionId | null>(null);

  React.useEffect(() => {
    if (pathname !== "/") {
      setActiveSection(null);
      return;
    }

    function updateActiveSection() {
      let current: SectionId | null = null;

      for (const id of SECTION_IDS) {
        const element = document.getElementById(id);
        if (!element) continue;

        const { top, bottom } = element.getBoundingClientRect();
        if (top <= HEADER_OFFSET && bottom > HEADER_OFFSET) {
          current = id;
          break;
        }
      }

      setActiveSection((previous) => (previous === current ? previous : current));
    }

    let frame = 0;
    function scheduleUpdate() {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(updateActiveSection);
    }

    updateActiveSection();

    // As seções da home podem chegar depois da hidratação (Suspense/streaming);
    // o observer garante que o scrollspy as encontre quando entrarem no DOM.
    const observer = new MutationObserver(scheduleUpdate);
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("scroll", scheduleUpdate, { passive: true });
    window.addEventListener("resize", scheduleUpdate);
    window.addEventListener("hashchange", scheduleUpdate);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("scroll", scheduleUpdate);
      window.removeEventListener("resize", scheduleUpdate);
      window.removeEventListener("hashchange", scheduleUpdate);
    };
  }, [pathname]);

  const catalogActive = pathname === "/catalog" || pathname.startsWith("/catalog/");

  return (
    <nav aria-label={t("nav.primary")} className="hidden items-center gap-0.5 lg:flex">
      <Link
        href="/catalog"
        aria-current={catalogActive ? "page" : undefined}
        className={`${navLinkClass} ${catalogActive ? activeNavLinkClass : ""}`}
      >
        {t("catalog.title")}
      </Link>
      <Link
        href="/#solucoes"
        aria-current={activeSection === "solucoes" ? "location" : undefined}
        className={`${navLinkClass} ${activeSection === "solucoes" ? activeNavLinkClass : ""}`}
      >
        {t("nav.solutions")}
      </Link>
      <Link
        href="/#a-forja"
        aria-current={activeSection === "a-forja" ? "location" : undefined}
        className={`${navLinkClass} ${activeSection === "a-forja" ? activeNavLinkClass : ""}`}
      >
        {t("nav.about")}
      </Link>
    </nav>
  );
}
