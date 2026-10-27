import type { Metadata } from "next";
import { ArrowUp } from "lucide-react";
import { getMessages, getTranslations } from "next-intl/server";

import { SiteFooter } from "@/shared/components/site-footer";
import { SiteHeader } from "@/shared/components/site-header";

interface PrivacyItem {
  term?: string;
  description?: string;
}

interface PrivacySection {
  title?: string;
  body?: string;
  note?: string;
  items?: PrivacyItem[];
  steps?: string[];
}

interface PrivacyMessages {
  sections?: PrivacySection[];
}

interface PrivacyPageProps {
  params: { locale: string };
}

const listClass = "text-sm leading-relaxed text-white/65";

const termClass = "font-semibold text-white";

const dashClass = "mx-2 text-white/30";

const bodyClass = "mt-4 max-w-2xl text-sm leading-relaxed text-white/65";

const noteClass = "mt-4 max-w-2xl text-sm leading-relaxed text-white/45";

const headingClass = "text-lg font-bold uppercase tracking-[0.14em] text-white";

export async function generateMetadata({ params }: PrivacyPageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  return { title: t("privacy.title"), description: t("privacy.heroNote") };
}

function renderItems(items: PrivacyItem[]) {
  return (
    <ul className="mt-5 list-disc space-y-3 ps-5 marker:text-white/30">
      {items.map((item, index) => (
        <li key={index} className={listClass}>
          {item.term ? (
            <>
              <strong className={termClass}>{item.term}</strong>
              <span aria-hidden="true" className={dashClass}>
                —
              </span>
            </>
          ) : null}
          {item.description}
        </li>
      ))}
    </ul>
  );
}

export default async function PrivacyPage({ params }: PrivacyPageProps) {
  const { locale } = params;
  const t = await getTranslations({ locale });
  const messages = await getMessages({ locale });
  const sections = (messages.privacy as unknown as PrivacyMessages | undefined)?.sections ?? [];
  const lastUpdated = t("privacy.lastUpdated", {
    date: t("privacy.date"),
    version: t("privacy.version"),
  });

  return (
    <>
      <SiteHeader />
      <main id="main" className="surface-ink flex-1">
        <div className="amber-glow border-b border-white/10">
          <div className="container py-16 lg:py-20">
            <div className="mx-auto max-w-3xl">
              <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.22em] text-primary">
                <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-primary" />
                {t("privacy.heroEyebrow")}
              </span>
              <h1 className="mt-6 text-4xl font-black tracking-tight text-white sm:text-5xl">
                {t("privacy.title")}
              </h1>
              <p className="mt-4 max-w-xl text-base leading-relaxed text-white/60">
                {t("privacy.heroNote")}
              </p>
              <p className="mt-4 text-xs uppercase tracking-[0.18em] text-white/45">
                {lastUpdated}
              </p>
            </div>
          </div>
        </div>

        <div className="container py-14 lg:py-16">
          <div className="mx-auto max-w-3xl space-y-14">
            {sections.map((section, index) => {
              const sectionId = `privacy-section-${index + 1}`;
              return (
                <section key={sectionId} aria-labelledby={sectionId} className="scroll-mt-24">
                  {section.title ? (
                    <h2 id={sectionId} className={headingClass}>
                      {section.title}
                    </h2>
                  ) : null}
                  {section.body ? <p className={bodyClass}>{section.body}</p> : null}
                  {section.items ? <div>{renderItems(section.items)}</div> : null}
                  {section.steps ? (
                    <ol className="mt-5 list-decimal space-y-3 ps-5 marker:text-white/30">
                      {section.steps.map((step, stepIndex) => (
                        <li key={stepIndex} className={listClass}>
                          {step}
                        </li>
                      ))}
                    </ol>
                  ) : null}
                  {section.note ? <p className={noteClass}>{section.note}</p> : null}
                </section>
              );
            })}

            <section
              aria-labelledby="privacy-contact"
              className="scroll-mt-24 border-t border-white/10 pt-8"
            >
              <h2 id="privacy-contact" className={headingClass}>
                {t("privacy.contactTitle")}
              </h2>
              <p className={bodyClass}>{t("privacy.contactLead")}</p>
              <a
                href={`mailto:${t("privacy.contactEmail")}`}
                className="mt-2 inline-block text-sm font-semibold text-primary underline underline-offset-4 transition-colors hover:text-forge-600"
              >
                {t("privacy.contactEmail")}
              </a>
            </section>

            <p className="text-xs uppercase tracking-[0.18em] text-white/40">{lastUpdated}</p>
          </div>
        </div>

        <div className="border-t border-white/10">
          <div className="container py-6 text-center">
            <a
              href="#main"
              aria-label={t("privacy.backToTop")}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-white/[0.04] text-white/70 transition-colors hover:border-primary/40 hover:text-primary"
            >
              <ArrowUp aria-hidden="true" className="h-4 w-4" />
            </a>
          </div>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
