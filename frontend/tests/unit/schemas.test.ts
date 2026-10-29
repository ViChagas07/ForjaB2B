import { describe, expect, it } from "vitest";

import { loginFormSchema } from "@/features/auth/schemas";
import { registerCompanyFormSchema } from "@/features/companies/schemas";
import { registerConsumerFormSchema } from "@/features/consumers/schemas";

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
    consent: true,
  };

  it("aceita dados válidos (com máscaras)", () => {
    expect(registerCompanyFormSchema.safeParse(valid).success).toBe(true);
  });

  it("rejeita sem aceite dos termos e da política de privacidade", () => {
    const result = registerCompanyFormSchema.safeParse({ ...valid, consent: false });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("onboarding.consentRequired");
    }
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

describe("registerConsumerFormSchema", () => {
  const valid = {
    full_name: "Cliente Teste",
    email: "cliente@teste.com",
    password: "Senha@Forte123",
    birth_date: "1990-01-01",
    cpf: "529.982.247-25",
    postal_code: "01001-000",
    gender: "PREFIRO_NAO_INFORMAR" as const,
    consent: true,
  };

  it("aceita dados válidos (com máscaras)", () => {
    expect(registerConsumerFormSchema.safeParse(valid).success).toBe(true);
  });

  it("rejeita CPF inválido", () => {
    const result = registerConsumerFormSchema.safeParse({ ...valid, cpf: "52998224726" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("consumer.cpfInvalid");
    }
  });

  it("rejeita menor de 18 anos", () => {
    const result = registerConsumerFormSchema.safeParse({ ...valid, birth_date: "2015-01-01" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("consumer.birthDateMinAge");
    }
  });

  it("rejeita data de nascimento inexistente", () => {
    const result = registerConsumerFormSchema.safeParse({ ...valid, birth_date: "2024-02-31" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("consumer.birthDateInvalid");
    }
  });

  it("rejeita CEP fora do formato", () => {
    const result = registerConsumerFormSchema.safeParse({ ...valid, postal_code: "123" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("consumer.postalCodeInvalid");
    }
  });

  it("exige aceite dos termos e da política de privacidade", () => {
    const result = registerConsumerFormSchema.safeParse({ ...valid, consent: false });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("onboarding.consentRequired");
    }
  });
});
