import createMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";

import { routing } from "./i18n/routing";
import { buildContentSecurityPolicy, generateNonce } from "./shared/security/csp";

const intlMiddleware = createMiddleware(routing);

const isProduction = process.env.NODE_ENV === "production";
const apiUrl = process.env.NEXT_PUBLIC_API_URL;

function withSecurityHeaders(response: NextResponse, nonce: string, csp: string): NextResponse {
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set(
    "Permissions-Policy",
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), " +
      "microphone=(), payment=(), usb=(), interest-cohort=()",
  );
  response.headers.set("X-Nonce", nonce);
  if (isProduction) {
    response.headers.set(
      "Strict-Transport-Security",
      "max-age=31536000; includeSubDomains",
    );
  }
  return response;
}

export default function middleware(request: NextRequest): NextResponse {
  const nonce = generateNonce();
  const csp = buildContentSecurityPolicy({ nonce, apiUrl, isProduction });

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  // O Next.js le este cabecalho da requisicao para aplicar o nonce aos scripts
  // gerados pelo framework; a resposta tambem o repete para o navegador.
  requestHeaders.set("Content-Security-Policy", csp);
  const requestWithNonce = new NextRequest(request, { headers: requestHeaders });

  const response = intlMiddleware(requestWithNonce);
  return withSecurityHeaders(response, nonce, csp);
}

export const config = {
  // Ignora: api, arquivos internos do Next e estáticos (com ponto no nome).
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
