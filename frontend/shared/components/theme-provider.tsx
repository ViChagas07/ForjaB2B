"use client";

import * as React from "react";

import {
  ACCENT_COLORS,
  useUiStore,
  type Accent,
  type FontSize,
  type Theme,
} from "@/shared/stores/ui-store";

const THEME_KEY = "forja-theme";
const ACCENT_KEY = "forja-accent";
const FONT_KEY = "forja-font-size";

function isTheme(value: string | null): value is Theme {
  return value === "light" || value === "dark" || value === "system";
}

function isAccent(value: string | null): value is Accent {
  return value !== null && value in ACCENT_COLORS;
}

function isFontSize(value: string | null): value is FontSize {
  return value === "small" || value === "normal" || value === "large";
}

/**
 * Sincroniza tema, cor de destaque e tamanho de fonte com o DOM/localStorage.
 * A fonte de verdade e o Zustand (ui-store).
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = useUiStore((s) => s.theme);
  const accent = useUiStore((s) => s.accent);
  const fontSize = useUiStore((s) => s.fontSize);
  const [systemDark, setSystemDark] = React.useState(false);

  React.useEffect(() => {
    const storedTheme = window.localStorage.getItem(THEME_KEY);
    const storedAccent = window.localStorage.getItem(ACCENT_KEY);
    const storedFont = window.localStorage.getItem(FONT_KEY);
    if (isTheme(storedTheme)) useUiStore.getState().setTheme(storedTheme);
    else if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
      useUiStore.getState().setTheme("system");
    }
    if (isAccent(storedAccent)) useUiStore.getState().setAccent(storedAccent);
    if (isFontSize(storedFont)) useUiStore.getState().setFontSize(storedFont);
  }, []);

  React.useEffect(() => {
    if (!window.matchMedia) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setSystemDark(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  const effectiveTheme: "light" | "dark" =
    theme === "system" ? (systemDark ? "dark" : "light") : theme;

  React.useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", effectiveTheme === "dark");
    root.style.colorScheme = effectiveTheme;
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme, effectiveTheme]);

  React.useEffect(() => {
    const colors = ACCENT_COLORS[accent];
    const root = document.documentElement;
    root.style.setProperty("--primary", colors.primary);
    root.style.setProperty("--primary-foreground", colors.foreground);
    root.style.setProperty("--ring", colors.primary);
    window.localStorage.setItem(ACCENT_KEY, accent);
  }, [accent]);

  React.useEffect(() => {
    document.documentElement.dataset.fontSize = fontSize;
    window.localStorage.setItem(FONT_KEY, fontSize);
  }, [fontSize]);

  return <>{children}</>;
}
