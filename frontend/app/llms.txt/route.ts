import { locales } from "@/i18n/locales";

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

/**
 * llms.txt — índice legível por LLMs (AEO/GEO).
 *
 * Formato Markdown: título, resumo em citação e seções com links absolutos.
 * Serve também como ponto de entrada para crawlers de IA.
 */
export function GET() {
  const productLinks = locales
    .map(
      (locale) => `- [Forja B2B (${locale})](${BASE_URL}/${locale}): Página inicial da plataforma.`,
    )
    .join("\n");

  const body = [
    "# Forja B2B",
    "",
    "> Plataforma B2B para a indústria.",
    "",
    "## Produtos",
    productLinks,
    "",
  ].join("\n");

  return new Response(body, {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "public, max-age=3600",
    },
  });
}
