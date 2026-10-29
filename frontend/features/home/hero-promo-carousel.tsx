"use client";

import { useEffect, useRef, useState, type FocusEvent } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import {
  heroPromoImageForLocale,
  nextRandomPromoIndex,
  type HeroPromoBanner,
} from "@/features/home/hero-promo-banners";
import { Link } from "@/i18n/navigation";
import { cn } from "@/shared/lib/utils";

const AUTO_ROTATE_INTERVAL_MS = 8000;
const PREFETCH_DELAY_MS = 1800;
const DESKTOP_IMAGE_QUERY = "(min-width: 1024px)";

interface HeroPromoCarouselProps {
  banners: readonly HeroPromoBanner[];
  initialIndex?: number;
}

function usePrefersReducedMotion() {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setPrefersReducedMotion(mediaQuery.matches);
    update();
    mediaQuery.addEventListener("change", update);
    return () => mediaQuery.removeEventListener("change", update);
  }, []);

  return prefersReducedMotion;
}

export function HeroPromoCarousel({ banners, initialIndex = 0 }: HeroPromoCarouselProps) {
  const t = useTranslations();
  const locale = useLocale();
  const [activeIndex, setActiveIndex] = useState(() => {
    if (banners.length === 0) {
      return 0;
    }
    const normalized = initialIndex % banners.length;
    return normalized < 0 ? normalized + banners.length : normalized;
  });
  const [autoRotationStopped, setAutoRotationStopped] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [hasFocusWithin, setHasFocusWithin] = useState(false);
  const [rotationEpoch, setRotationEpoch] = useState(0);
  const prefersReducedMotion = usePrefersReducedMotion();
  const hasBeenVisibleRef = useRef(false);

  const activeBanner = banners[activeIndex] ?? banners[0];
  const hasMultipleBanners = banners.length > 1;

  useEffect(() => {
    if (banners.length < 2) {
      return;
    }

    const prefersLargeImage =
      window.matchMedia(DESKTOP_IMAGE_QUERY).matches || window.devicePixelRatio > 1;
    const timer = window.setTimeout(() => {
      for (const banner of banners) {
        const variant = heroPromoImageForLocale(banner, locale);
        const image = new window.Image();
        image.decoding = "async";
        image.src = prefersLargeImage ? variant.image.src : variant.image.smallSrc;
      }
    }, PREFETCH_DELAY_MS);

    return () => window.clearTimeout(timer);
  }, [banners, locale]);

  useEffect(() => {
    if (banners.length < 2) {
      return;
    }

    hasBeenVisibleRef.current = document.visibilityState === "visible";

    function handleVisibilityChange() {
      if (document.visibilityState !== "visible") {
        return;
      }
      if (hasBeenVisibleRef.current) {
        setActiveIndex((current) => nextRandomPromoIndex(current, banners.length));
        setRotationEpoch((value) => value + 1);
      }
      hasBeenVisibleRef.current = true;
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, [banners.length]);

  useEffect(() => {
    if (
      banners.length < 2 ||
      prefersReducedMotion ||
      autoRotationStopped ||
      isHovered ||
      hasFocusWithin
    ) {
      return;
    }

    const interval = window.setInterval(() => {
      if (document.visibilityState === "hidden") {
        return;
      }
      setActiveIndex((current) => (current + 1) % banners.length);
    }, AUTO_ROTATE_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [
    autoRotationStopped,
    banners.length,
    hasFocusWithin,
    isHovered,
    prefersReducedMotion,
    rotationEpoch,
  ]);

  function goTo(index: number) {
    setActiveIndex(index);
    setAutoRotationStopped(true);
  }

  function goPrevious() {
    goTo((activeIndex - 1 + banners.length) % banners.length);
  }

  function goNext() {
    goTo((activeIndex + 1) % banners.length);
  }

  function handleBlur(event: FocusEvent<HTMLDivElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setHasFocusWithin(false);
    }
  }

  if (!activeBanner) {
    return null;
  }

  const activeImage = heroPromoImageForLocale(activeBanner, locale);

  return (
    <div
      role="region"
      aria-label={t("home.promos.regionLabel")}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onFocus={() => setHasFocusWithin(true)}
      onBlur={handleBlur}
      className="relative"
    >
      <div className="overflow-hidden rounded-2xl border border-white/10 bg-ink shadow-[0_30px_80px_-52px_rgba(245,158,11,0.65)]">
        <Link
          href={activeBanner.href}
          aria-label={t(activeBanner.labelKey)}
          className="group relative block aspect-[8/5] max-h-56 w-full overflow-hidden bg-ink focus-visible:outline-none sm:aspect-[1760/638] sm:max-h-none"
        >
          <img
            key={activeBanner.id}
            src={activeImage.image.src}
            srcSet={activeImage.image.srcSet}
            sizes="(min-width: 1152px) 1152px, (min-width: 640px) calc(100vw - 3rem), 700px"
            width={activeImage.image.width}
            height={activeImage.image.height}
            alt=""
            loading="eager"
            decoding="async"
            draggable={false}
            className="h-full w-full animate-fade-in object-cover object-left sm:object-center"
          />
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 ring-2 ring-inset ring-primary transition-opacity group-focus-visible:opacity-100"
          />
        </Link>

        {hasMultipleBanners ? (
          <div className="flex items-center justify-between gap-3 border-t border-white/10 bg-[#0d0d0e]/95 px-3 py-2 sm:px-4">
            <div className="flex items-center gap-1">
              {banners.map((banner, index) => {
                const isActive = index === activeIndex;
                return (
                  <button
                    key={banner.id}
                    type="button"
                    onClick={() => goTo(index)}
                    aria-label={t("home.promos.goTo", {
                      index: index + 1,
                      title: t(banner.labelKey),
                    })}
                    aria-current={isActive ? "true" : undefined}
                    className="group flex h-8 min-w-6 items-center justify-center rounded-full px-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        "block h-1.5 rounded-full transition-all",
                        isActive ? "w-7 bg-primary" : "w-3 bg-white/30 group-hover:bg-white/55",
                      )}
                    />
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-2">
              <span
                aria-hidden="true"
                dir="ltr"
                className="hidden text-[10px] font-semibold tabular-nums tracking-[0.18em] text-white/45 sm:inline"
              >
                {activeIndex + 1} / {banners.length}
              </span>
              <button
                type="button"
                onClick={goPrevious}
                aria-label={t("home.promos.previous")}
                className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/65 transition-colors hover:border-primary/40 hover:bg-primary/15 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
              >
                <ChevronLeft aria-hidden="true" className="h-4 w-4 rtl:-scale-x-100" />
              </button>
              <button
                type="button"
                onClick={goNext}
                aria-label={t("home.promos.next")}
                className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/65 transition-colors hover:border-primary/40 hover:bg-primary/15 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
              >
                <ChevronRight aria-hidden="true" className="h-4 w-4 rtl:-scale-x-100" />
              </button>
            </div>
          </div>
        ) : null}
      </div>

      {hasMultipleBanners ? (
        <>
          <button
            type="button"
            onClick={goPrevious}
            aria-label={t("catalog.previous")}
            className="absolute start-0 top-[calc(50%_-_1.5rem)] z-10 inline-flex h-10 w-10 -translate-x-1/2 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full border border-primary/50 bg-ink/80 text-primary shadow-[0_14px_36px_-10px_rgba(0,0,0,0.95)] backdrop-blur-md transition-colors hover:border-primary/80 hover:bg-primary/25 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-ink rtl:translate-x-1/2 sm:h-12 sm:w-12"
          >
            <ChevronLeft aria-hidden="true" className="h-4 w-4 rtl:-scale-x-100 sm:h-5 sm:w-5" />
          </button>
          <button
            type="button"
            onClick={goNext}
            aria-label={t("catalog.next")}
            className="absolute end-0 top-[calc(50%_-_1.5rem)] z-10 inline-flex h-10 w-10 -translate-y-1/2 translate-x-1/2 cursor-pointer items-center justify-center rounded-full border border-primary/50 bg-ink/80 text-primary shadow-[0_14px_36px_-10px_rgba(0,0,0,0.95)] backdrop-blur-md transition-colors hover:border-primary/80 hover:bg-primary/25 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-ink rtl:-translate-x-1/2 sm:h-12 sm:w-12"
          >
            <ChevronRight aria-hidden="true" className="h-4 w-4 rtl:-scale-x-100 sm:h-5 sm:w-5" />
          </button>
        </>
      ) : null}

      {hasMultipleBanners ? (
        <p aria-live="polite" aria-atomic="true" className="sr-only">
          {t("home.promos.status", {
            current: activeIndex + 1,
            total: banners.length,
          })}
        </p>
      ) : null}
    </div>
  );
}
