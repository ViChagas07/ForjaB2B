import type { Gender } from "@/core/domain/account";

export const DASHBOARD_COVERS = {
  masculine: "/covers/dashboard-masculino.jpg",
  feminine: "/covers/dashboard-feminino.jpg",
  neutral: "/covers/dashboard-generico.webp",
} as const;

/**
 * Capa do painel conforme o gênero declarado no perfil.
 *
 * Não-binário, outro, preferência por não informar e contas sem gênero usam a
 * arte neutra. Contas empresariais também caem na arte neutra.
 */
export function dashboardCoverForGender(gender: Gender | null | undefined): string {
  if (gender === "MASCULINO") return DASHBOARD_COVERS.masculine;
  if (gender === "FEMININO") return DASHBOARD_COVERS.feminine;
  return DASHBOARD_COVERS.neutral;
}
