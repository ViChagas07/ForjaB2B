import { z, type RefinementCtx } from "zod";

/**
 * Schema de validação do formulário de login.
 *
 * As mensagens são chaves de tradução (resolvidas via `t()` na UI), mantendo
 * a validação estrutural separada da localização. Os limites espelham o
 * contrato do backend (`LoginRequest`: email até 320, senha até 128).
 */

export const loginFormSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "auth.emailRequired")
    .max(320, "auth.emailTooLong")
    .email("auth.emailInvalid"),
  password: z.string().min(1, "auth.passwordRequired").max(128, "auth.passwordTooLong"),
});

export type LoginFormValues = z.infer<typeof loginFormSchema>;


const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PHONE_ALLOWED_RE = /^\+[0-9()\s.\-]+$/;
const E164_RE = /^\+[1-9]\d{7,14}$/;
const BR_NATIONAL_RE = /^[1-9][1-9]\d{8,9}$/;

/** Mesma regra do backend: E.164 explicito, Brasil com DDD e 10/11 digitos. */
export function normalizePhoneE164(value: string): string | null {
  const raw = value.trim();
  if (!raw || !PHONE_ALLOWED_RE.test(raw)) return null;
  const digits = raw.replace(/\D/g, "");
  if (digits.startsWith("55")) {
    const national = digits.slice(2);
    return BR_NATIONAL_RE.test(national) ? `+55${national}` : null;
  }
  return E164_RE.test(`+${digits}`) ? `+${digits}` : null;
}

interface IdentifierData {
  email?: string;
  phone?: string;
}

function validateIdentifier(
  data: IdentifierData,
  ctx: RefinementCtx,
): void {
  const email = data.email?.trim() ?? "";
  const phone = data.phone?.trim() ?? "";
  if (!email && !phone) {
    ctx.addIssue({
      code: "custom",
      path: ["email"],
      message: "forgotPassword.identifierRequired",
    });
    return;
  }
  if (email && phone) {
    ctx.addIssue({
      code: "custom",
      path: ["phone"],
      message: "forgotPassword.identifierRequired",
    });
  }
  if (email && !EMAIL_RE.test(email)) {
    ctx.addIssue({
      code: "custom",
      path: ["email"],
      message: "forgotPassword.emailInvalid",
    });
  }
  if (phone && !normalizePhoneE164(phone)) {
    ctx.addIssue({
      code: "custom",
      path: ["phone"],
      message: "forgotPassword.phoneInvalid",
    });
  }
}

function normalizedIdentifier(data: IdentifierData): {
  email?: string;
  phone?: string;
} {
  const email = data.email?.trim().toLowerCase();
  const phone = data.phone?.trim();
  return {
    email: email || undefined,
    phone: phone ? (normalizePhoneE164(phone) ?? undefined) : undefined,
  };
}

export const passwordRecoveryRequestSchema = z
  .object({
    email: z.string().trim().optional(),
    phone: z.string().trim().optional(),
    turnstile_token: z.string().trim().min(1, "forgotPassword.turnstileRequired"),
    locale: z.string().optional(),
  })
  .superRefine(validateIdentifier)
  .transform((data) => ({ ...data, ...normalizedIdentifier(data) }));

export type PasswordRecoveryRequestValues = z.infer<typeof passwordRecoveryRequestSchema>;

export const passwordRecoveryVerifySchema = z
  .object({
    email: z.string().trim().optional(),
    phone: z.string().trim().optional(),
    code: z.string().trim().regex(/^\d{6}$/, "forgotPassword.codeInvalid"),
  })
  .superRefine(validateIdentifier)
  .transform((data) => ({ ...data, ...normalizedIdentifier(data) }));

export type PasswordRecoveryVerifyValues = z.infer<typeof passwordRecoveryVerifySchema>;

export const passwordRecoveryResetSchema = z
  .object({
    new_password: z
      .string()
      .min(8, "forgotPassword.passwordMin")
      .max(128, "forgotPassword.passwordMax"),
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    path: ["confirm_password"],
    message: "forgotPassword.passwordMismatch",
  });

export type PasswordRecoveryResetValues = z.infer<typeof passwordRecoveryResetSchema>;

export const phoneVerificationStartSchema = z
  .object({
    phone: z.string().trim().min(1, "account.phoneRequired"),
  })
  .superRefine((data, ctx) => {
    if (!normalizePhoneE164(data.phone)) {
      ctx.addIssue({
        code: "custom",
        path: ["phone"],
        message: "account.phoneInvalid",
      });
    }
  })
  .transform((data) => ({ phone: normalizePhoneE164(data.phone) as string }));

export type PhoneVerificationStartValues = z.infer<typeof phoneVerificationStartSchema>;

export const phoneVerificationCheckSchema = z
  .object({
    phone: z.string().trim().min(1, "account.phoneRequired"),
    code: z.string().trim().regex(/^\d{6}$/, "account.phoneCodeRequired"),
  })
  .superRefine((data, ctx) => {
    if (!normalizePhoneE164(data.phone)) {
      ctx.addIssue({
        code: "custom",
        path: ["phone"],
        message: "account.phoneInvalid",
      });
    }
  })
  .transform((data) => ({
    phone: normalizePhoneE164(data.phone) as string,
    code: data.code,
  }));
