import { create } from "zustand";

/**
 * Estado de UI (cliente) via Zustand.
 *
 * Reservado para preferencias e estado transitorio de UI. NAO deve virar cache
 * de dados do servidor (isso e responsabilidade do TanStack Query).
 */

export type Theme = "light" | "dark" | "system";
export type Accent = "amber" | "red" | "violet" | "blue" | "pink" | "yellow" | "green" | "cyan";
export type FontSize = "small" | "normal" | "large";

export const ACCENTS: readonly Accent[] = [
  "amber",
  "red",
  "violet",
  "blue",
  "pink",
  "yellow",
  "green",
  "cyan",
];

export const ACCENT_COLORS: Record<Accent, { primary: string; foreground: string }> = {
  amber: { primary: "38 92% 50%", foreground: "0 0% 4%" },
  red: { primary: "0 72% 51%", foreground: "0 0% 100%" },
  violet: { primary: "262 83% 58%", foreground: "0 0% 100%" },
  blue: { primary: "217 91% 60%", foreground: "0 0% 100%" },
  pink: { primary: "330 81% 60%", foreground: "0 0% 100%" },
  yellow: { primary: "48 96% 53%", foreground: "0 0% 4%" },
  green: { primary: "152 60% 42%", foreground: "0 0% 4%" },
  cyan: { primary: "189 94% 43%", foreground: "0 0% 4%" },
};

interface UiState {
  theme: Theme;
  accent: Accent;
  fontSize: FontSize;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  setAccent: (accent: Accent) => void;
  setFontSize: (fontSize: FontSize) => void;
}

export const useUiStore = create<UiState>()((set) => ({
  theme: "light",
  accent: "amber",
  fontSize: "normal",
  setTheme: (theme) => set({ theme }),
  toggleTheme: () => set((state) => ({ theme: state.theme === "dark" ? "light" : "dark" })),
  setAccent: (accent) => set({ accent }),
  setFontSize: (fontSize) => set({ fontSize }),
}));
