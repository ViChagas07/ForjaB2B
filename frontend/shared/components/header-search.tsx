"use client";

import * as React from "react";
import { ArrowRight, Search } from "lucide-react";
import { useTranslations } from "next-intl";

import { useRouter } from "@/i18n/navigation";
import { cn } from "@/shared/lib/utils";
import { Input } from "@/shared/ui/input";

interface HeaderSearchProps {
  className?: string;
  inputClassName?: string;
}

export function HeaderSearch({ className, inputClassName }: HeaderSearchProps) {
  const t = useTranslations();
  const router = useRouter();
  const [query, setQuery] = React.useState("");

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    router.push(value ? `/catalog?q=${encodeURIComponent(value)}` : "/catalog");
  }

  return (
    <form role="search" onSubmit={handleSubmit} className={cn("relative w-full", className)}>
      <Search
        aria-hidden="true"
        className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/60"
      />
      <Input
        type="search"
        value={query}
        aria-label={t("nav.searchLabel")}
        placeholder={t("nav.searchPlaceholder")}
        onChange={(event) => setQuery(event.target.value)}
        className={cn(
          "h-10 rounded-xl border-white/10 bg-white/[0.06] pe-11 ps-9 text-sm text-white shadow-none placeholder:text-white/60 focus-visible:border-primary/50 focus-visible:ring-primary",
          inputClassName,
        )}
      />
      <button
        type="submit"
        aria-label={t("nav.searchSubmit")}
        className="absolute end-1.5 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
      >
        <ArrowRight aria-hidden="true" className="h-3.5 w-3.5 rtl:-scale-x-100" />
      </button>
    </form>
  );
}
