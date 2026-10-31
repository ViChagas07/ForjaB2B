/** Limites do avatar do perfil, espelhando a validacao do backend. */

export const AVATAR_MAX_BYTES = 2 * 1024 * 1024;
export const AVATAR_ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export const AVATAR_ACCEPT = AVATAR_ACCEPTED_TYPES.join(",");

export function isAcceptedAvatarType(type: string): boolean {
  return (AVATAR_ACCEPTED_TYPES as readonly string[]).includes(type);
}
