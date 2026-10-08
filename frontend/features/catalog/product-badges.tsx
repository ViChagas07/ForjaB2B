"use client";

import { useTranslations } from "next-intl";

import type { CaStatus } from "@/core/domain/catalog";
import { Badge } from "@/shared/ui/badge";

function caVariant(status: CaStatus) {
  switch (status) {
    case "VALID":
      return "success" as const;
    case "EXPIRED":
    case "MISSING":
      return "warning" as const;
    default:
      return "secondary" as const;
  }
}

function caLabelKey(status: CaStatus) {
  switch (status) {
    case "VALID":
      return "catalog.caValid";
    case "EXPIRED":
      return "catalog.caExpired";
    case "MISSING":
      return "catalog.caMissing";
    default:
      return "catalog.caNotApplicable";
  }
}

/** Badge de status do CA (derivado no backend, apenas exibido aqui). */
export function CaStatusBadge({ status }: { status: CaStatus }) {
  const t = useTranslations();
  return <Badge variant={caVariant(status)}>{t(caLabelKey(status))}</Badge>;
}

/** Badge indicando se o produto é EPI. */
export function EpiBadge({ isEpi }: { isEpi: boolean }) {
  const t = useTranslations();
  if (!isEpi) {
    return null;
  }
  return <Badge variant="info">{t("catalog.epi")}</Badge>;
}

/** Badge de indisponibilidade para produtos não vendáveis/exibivel. */
export function AvailabilityBadge({ isSellable }: { isSellable: boolean }) {
  const t = useTranslations();
  if (isSellable) {
    return null;
  }
  return <Badge variant="destructive">{t("catalog.notSellable")}</Badge>;
}
