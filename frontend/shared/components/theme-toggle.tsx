"use client";

import { Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";

import { useUiStore } from "@/shared/stores/ui-store";
import { Button } from "@/shared/ui/button";

export function ThemeToggle() {
  const theme = useUiStore((s) => s.theme);
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const t = useTranslations();

  const Icon = theme === "light" ? Sun : Moon;

  return (
    <Button variant="ghost" size="icon" aria-label={t("themeLabel")} onClick={toggleTheme}>
      <Icon className="h-4 w-4" aria-hidden="true" />
    </Button>
  );
}
