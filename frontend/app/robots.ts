import type { MetadataRoute } from "next";

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

/**
 * robots.txt base.
 *
 * NOTA: a decisão de bloquear/liberar crawlers de IA (GPTBot, ClaudeBot,
 * PerplexityBot, Google-Extended) é do dono do produto e ainda não foi
 * tomada — por isso nenhuma regra específica é aplicada aqui.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
    },
    sitemap: `${BASE_URL}/sitemap.xml`,
  };
}
