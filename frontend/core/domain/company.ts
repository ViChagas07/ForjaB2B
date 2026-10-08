/**
 * Contratos do contexto de empresas (neutros, sem frameworks).
 *
 * Campos em snake_case para refletir o JSON real do backend. `Company` é a
 * visão pública da empresa (sem dados sensíveis); `RegisterCompanyInput` é a
 * entrada do onboarding (empresa + operador inicial ADMIN).
 */

export const COMPANY_STATUSES = ["PENDING", "ACTIVE", "SUSPENDED", "REJECTED"] as const;

export type CompanyStatus = (typeof COMPANY_STATUSES)[number];

export interface Company {
  id: string;
  cnpj: string;
  legal_name: string;
  trade_name: string | null;
  status: CompanyStatus;
}

export interface RegisterCompanyInput {
  cnpj: string;
  legal_name: string;
  trade_name: string | null;
  admin_full_name: string;
  admin_email: string;
  admin_cpf: string;
  password: string;
}

export interface RegisterCompanyResult {
  company: Company;
  admin_user_id: string;
}
