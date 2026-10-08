"use client";

import * as React from "react";
import { LogOut } from "lucide-react";
import { useTranslations } from "next-intl";

import { useRouter } from "@/i18n/navigation";
import { logout } from "@/shared/stores/auth-actions";
import { Button } from "@/shared/ui/button";

export function LogoutButton() {
  const t = useTranslations();
  const router = useRouter();
  const [isLoading, setIsLoading] = React.useState(false);

  async function handleLogout() {
    setIsLoading(true);
    try {
      await logout();
      router.replace("/login");
      router.refresh();
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Button variant="outline" size="sm" disabled={isLoading} onClick={handleLogout}>
      <LogOut className="h-4 w-4" aria-hidden="true" />
      {isLoading ? t("auth.logoutLoading") : t("auth.logout")}
    </Button>
  );
}
