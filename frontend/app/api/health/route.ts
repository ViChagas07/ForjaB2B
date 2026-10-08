import { NextResponse } from "next/server";

/**
 * Health do frontend (liveness).
 *
 * Indica apenas que o processo Next.js está operacional. NÃO depende de
 * PostgreSQL/Redis nem expõe detalhes internos. O healthcheck do
 * docker-compose usa este endpoint (ou `/` como fallback).
 */
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({
    status: "ok",
    service: "forja-frontend",
    timestamp: new Date().toISOString(),
  });
}
