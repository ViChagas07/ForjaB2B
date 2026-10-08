import { afterEach, describe, expect, it, vi } from "vitest";

import type { RegisterCompanyInput } from "@/core/domain/company";
import { companyApi } from "@/infrastructure/http";

function jsonResponse(body: unknown, init?: { status?: number; contentType?: string }): Response {
  return new Response(JSON.stringify(body), {
    status: init?.status ?? 200,
    headers: { "content-type": init?.contentType ?? "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const REGISTER_INPUT: RegisterCompanyInput = {
  cnpj: "11222333000181",
  legal_name: "Empresa Teste Ltda",
  trade_name: "Empresa Teste",
  admin_full_name: "Admin Teste",
  admin_email: "admin@teste.com",
  admin_cpf: "52998224725",
  password: "Senha@Forte123",
};

describe("companyApi.register", () => {
  it("registra a empresa e devolve o resultado (201)", async () => {
    const body = {
      company: {
        id: "company-1",
        cnpj: "11222333000181",
        legal_name: "Empresa Teste Ltda",
        trade_name: "Empresa Teste",
        status: "PENDING",
      },
      admin_user_id: "user-1",
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(body, { status: 201 })));

    const result = await companyApi.register(REGISTER_INPUT);

    expect(result.company.status).toBe("PENDING");
    expect(result.company.cnpj).toBe("11222333000181");
    expect(result.admin_user_id).toBe("user-1");
  });

  it("normaliza trade_name vazio para null no corpo enviado", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          company: {
            id: "c",
            cnpj: "11222333000181",
            legal_name: "X",
            trade_name: null,
            status: "PENDING",
          },
          admin_user_id: "u",
        },
        { status: 201 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await companyApi.register({ ...REGISTER_INPUT, trade_name: "" });

    const [, init] = fetchMock.mock.calls[0] ?? [null, {}];
    const sentBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
    expect(sentBody.trade_name).toBeNull();
    expect(sentBody.cnpj).toBe("11222333000181");
  });

  it("mapeia CNPJ inválido para ApiError RFC 7807", async () => {
    const problem = {
      type: "urn:forja:problem:invalid_cnpj",
      title: "Domain Error",
      status: 400,
      detail: "CNPJ invalido.",
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(problem, { status: 400, contentType: "application/problem+json" }),
        ),
    );

    await expect(companyApi.register(REGISTER_INPUT)).rejects.toMatchObject({
      code: "urn:forja:problem:invalid_cnpj",
      status: 400,
    });
  });
});

describe("companyApi.getMe", () => {
  it("consulta a empresa do tenant com Authorization Bearer", async () => {
    const company = {
      id: "company-1",
      cnpj: "11222333000181",
      legal_name: "Empresa Teste Ltda",
      trade_name: null,
      status: "ACTIVE",
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(company));
    vi.stubGlobal("fetch", fetchMock);

    const result = await companyApi.getMe("access-token");

    expect(result.status).toBe("ACTIVE");
    const [, init] = fetchMock.mock.calls[0] ?? [null, {}];
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer access-token");
  });
});
