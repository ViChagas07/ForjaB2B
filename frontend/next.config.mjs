import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

// `next lint` carrega a config com a fase de build; por isso a validação
// olha o subcomando real. O build (inclusive na Vercel) inclui "build".
const isProductionBuild =
  process.argv.includes("build") || process.env.npm_lifecycle_event === "build";

/**
 * URL de servidor do backend. Fica fora do bundle do navegador: o browser
 * sempre chama `/api/v1` na própria origem da Vercel.
 *
 * Rewrites são resolvidos no build; por isso a variável precisa existir no
 * painel da Vercel antes do deploy de produção.
 */
function resolveBackendUrl() {
  const configured = process.env.BACKEND_URL?.trim();
  if (!configured) {
    if (isProductionBuild) {
      throw new Error(
        "BACKEND_URL não definida. Configure a variável de servidor no painel da Vercel " +
          "(valor esperado: https://forjab2b.onrender.com) e faça um novo deploy; " +
          "rewrites são resolvidos no build.",
      );
    }
    return "http://localhost:8000";
  }

  const normalized = configured.replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(normalized)) {
    throw new Error(
      "BACKEND_URL inválida: use uma URL absoluta http(s), por exemplo " +
        "https://forjab2b.onrender.com.",
    );
  }
  return normalized;
}

const backendUrl = resolveBackendUrl();

/** @type {import('next').NextConfig} */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  {
    key: "Permissions-Policy",
    value:
      "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), " +
      "microphone=(), payment=(), usb=(), interest-cohort=()",
  },
];

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  // O redirect de barra final fica no dominio do frontend (308) antes do
  // rewrite; sem isso, o redirect_slashes do FastAPI poderia apontar para o
  // dominio do Render e tirar o navegador da origem da Vercel.
  trailingSlash: false,
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
      {
        // Imagens/ilustrações versionadas da API passam a ser same-origin,
        // sem exigir uma URL de backend no bundle do navegador.
        source: "/static/:path*",
        destination: `${backendUrl}/static/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        // Aplica tambem a assets estaticos (a CSP e definida no middleware,
        // onde o nonce por requisicao e gerado).
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
