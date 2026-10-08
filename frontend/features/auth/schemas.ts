import { z } from "zod";

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
