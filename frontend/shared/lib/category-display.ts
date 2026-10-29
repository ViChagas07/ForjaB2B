/**
 * Nomes legados de categorias que podem existir em bancos já semeados.
 * O banco é corrigido por migration/seed, mas este fallback garante que a
 * interface continue correta durante o deploy do frontend.
 */
const LEGACY_CATEGORY_NAMES: Record<string, string> = {
  "maquinas e ferramentas": "Máquinas e Ferramentas",
};

export function displayCategoryName(name: string): string {
  const normalized = name.trim().toLowerCase();
  return LEGACY_CATEGORY_NAMES[normalized] ?? name;
}
