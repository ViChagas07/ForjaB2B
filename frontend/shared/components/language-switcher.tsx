"use client";

import { Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { usePathname, useRouter } from "@/i18n/navigation";
import { isLocale, isRtlLocale, localeLabels, locales, type Locale } from "@/i18n/locales";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu";

interface LanguageSwitcherProps {
  className?: string;
}

export function LanguageSwitcher({ className }: LanguageSwitcherProps) {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  function onSelect(next: Locale) {
    if (next !== locale) {
      router.replace(pathname, { locale: next });
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={cn(className)}
          aria-label={`${t("languageLabel")}: ${isLocale(locale) ? localeLabels[locale] : locale}`}
        >
          <Languages className="h-4 w-4" aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {locales.map((code) => (
          <DropdownMenuItem
            key={code}
            lang={code}
            dir={isRtlLocale(code) ? "rtl" : undefined}
            aria-current={code === locale ? "true" : undefined}
            onSelect={() => onSelect(code)}
          >
            {localeLabels[code]}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
