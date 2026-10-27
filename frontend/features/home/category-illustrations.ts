/**
 * Fotos de categoria exibidas no molde redondo do card da seção
 * "Categorias para cada desafio". A chave é o nome da categoria
 * normalizado (sem acentos e em caixa baixa) para casar com variações
 * vindas da API. Categorias fora do mapa ficam apenas com o círculo
 * decorativo atual.
 */
const CATEGORY_ILLUSTRATIONS: Record<string, string> = {
  epis: "/catalog/illustrations/EPIs.jpg",
  "ferramentas eletricas": "/catalog/illustrations/Ferramentas Elétricas.jpg",
  "maquinas e ferramentas": "/catalog/illustrations/Máquinas e Ferramentas.jpg",
  "maquinas estacionarias": "/catalog/illustrations/Máquinas Estacionárias.jpg",
};

export function categoryIllustration(name: string): string | undefined {
  const key = name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
  return CATEGORY_ILLUSTRATIONS[key];
}
