import { describe, expect, it } from "vitest";

import { loginFormSchema } from "@/features/auth/schemas";
import { registerCompanyFormSchema } from "@/features/companies/schemas";

describe("loginFormSchema", () => {
  it("aceita credenciais válidas", () => {
    const result = loginFormSchema.safeParse({ email: "admin@empresa.com", password: "senha" });
    expect(result.success).toBe(true);
  });

  it("exige e-mail", () => {
    const result = loginFormSchema.safeParse({ email: "", password: "senha" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("auth.emailRequired");
    }
  });

  it("rejeita e-mail inválido", () => {
    const result = loginFormSchema.safeParse({ email: "nao-e-email", password: "senha" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("auth.emailInvalid");
    }
  });

  it("exige senha", () => {
    const result = loginFormSchema.safeParse({ email: "admin@empresa.com", password: "" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("auth.passwordRequired");
    }
  });
});

describe("registerCompanyFormSchema", () => {
  const valid = {
    cnpj: "11.222.333/0001-81",
    legal_name: "Empresa Teste Ltda",
    trade_name: "Empresa Teste",
    admin_full_name: "Admin Teste",
    admin_email: "admin@teste.com",
    admin_cpf: "529.982.247-25",
    password: "Senha@Forte123",
  };

  it("aceita dados válidos (com máscaras)", () => {
    expect(registerCompanyFormSchema.safeParse(valid).success).toBe(true);
  });

  it("rejeita CNPJ inválido", () => {
    const result = registerCompanyFormSchema.safeParse({ ...valid, cnpj: "11222333000182" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("onboarding.cnpjInvalid");
    }
  });

  it("rejeita CPF inválido", () => {
    const result = registerCompanyFormSchema.safeParse({ ...valid, admin_cpf: "52998224726" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("onboarding.adminCpfInvalid");
    }
  });

  it("rejeita senha curta", () => {
    const result = registerCompanyFormSchema.safeParse({ ...valid, password: "1234567" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("onboarding.passwordMin");
    }
  });

  it("rejeita razão social ausente", () => {
    const result = registerCompanyFormSchema.safeParse({ ...valid, legal_name: " " });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("onboarding.legalNameRequired");
    }
  });
});
