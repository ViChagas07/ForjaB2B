import Image from "next/image";
import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { cn } from "@/shared/lib/utils";

interface BrandLogoProps {
  className?: string;
  imageClassName?: string;
}

/**
 * Assinatura visual da Forja B2B. A versão clara preserva o símbolo âmbar e
 * troca as letras escuras por branco/cinza, permitindo uso direto sobre o
 * navbar e o rodapé pretos sem placa de fundo.
 */
export async function BrandLogo({ className, imageClassName }: BrandLogoProps) {
  const t = await getTranslations();

  return (
    <Link
      href="/"
      aria-label={t("appName")}
      className={cn("inline-flex shrink-0 items-center", className)}
    >
      <Image
        src="/brand/forja-b2b-logo-light.png"
        alt={t("appName")}
        width={600}
        height={174}
        priority
        unoptimized
        className={cn("h-8 w-auto sm:h-9", imageClassName)}
      />
    </Link>
  );
}
