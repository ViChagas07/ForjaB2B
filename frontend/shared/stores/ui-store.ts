import { create } from "zustand";

/**
 * Estado de UI (cliente) via Zustand.
 *
 * Reservado para preferências/estado transitório de UI. NÃO deve virar cache
 * de dados do servidor (isso é responsabilidade do TanStack Query). Nenhuma
 * store de negócio é criada nesta fase.
 */

export type Theme = "light" | "dark";

interface UiState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

export const useUiStore = create<UiState>()((set) => ({
  theme: "light",
  setTheme: (theme) => set({ theme }),
  toggleTheme: () => set((state) => ({ theme: state.theme === "light" ? "dark" : "light" })),
}));
