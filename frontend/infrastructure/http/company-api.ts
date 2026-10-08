import type { Company, RegisterCompanyInput, RegisterCompanyResult } from "@/core/domain/company";

import { apiClient } from "./client";

/**
 * Adapter HTTP para os endpoints de empresas (`/api/v1/companies`).
 *
 * O `company_id` usado na consulta autenticada (`getMe`) é derivado pelo
 * backend a partir do token de acesso (`Authorization: Bearer`); o frontend
 * NUNCA envia um `company_id` arbitrário para selecionar o tenant.
 */
export const companyApi = {
  async register(input: RegisterCompanyInput): Promise<RegisterCompanyResult> {
    const response = await apiClient.request<RegisterCompanyResult>({
      method: "POST",
      path: "/api/v1/companies",
      body: {
        cnpj: input.cnpj,
        legal_name: input.legal_name,
        trade_name: input.trade_name || null,
        admin_full_name: input.admin_full_name,
        admin_email: input.admin_email,
        admin_cpf: input.admin_cpf,
        password: input.password,
      },
    });
    return response.body;
  },

  async getMe(accessToken: string): Promise<Company> {
    const response = await apiClient.request<Company>({
      method: "GET",
      path: "/api/v1/companies/me",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.body;
  },
};
