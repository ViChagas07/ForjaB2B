import Image from "next/image";
import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { cn } from "@/shared/lib/utils";

interface BrandLogoProps {
  className?: string;
  imageClassName?: string;
  plate?: boolean;
}

/**
 * Assinatura visual da Forja B2B. O arquivo original tem letras escuras, então
 * sobre superfícies pretas ele é apresentado em uma placa branca para manter
 * contraste e legibilidade.
 */
export async function BrandLogo({ className, imageClassName, plate = true }: BrandLogoProps) {
  const t = await getTranslations();

  return (
    <Link
      href="/"
      aria-label={t("appName")}
      className={cn("inline-flex shrink-0 items-center gap-3", className)}
    >
      <span className={cn(plate && "logo-plate")}>
        <Image
          src="/brand/forja-b2b-logo.png"
          alt={t("appName")}
          width={600}
          height={174}
          priority
          unoptimized
          className={cn("h-8 w-auto sm:h-9", imageClassName)}
        />
      </span>
    </Link>
  );
}
