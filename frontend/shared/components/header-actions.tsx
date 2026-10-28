"use client";

import * as React from "react";
import { ChevronDown, LayoutDashboard, LogOut, Menu, ShoppingCart, UserRound } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link, useRouter } from "@/i18n/navigation";
import { AiChatWidget } from "@/features/ai-chat/ai-chat-widget";
import { logout } from "@/shared/stores/auth-actions";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Button } from "@/shared/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu";

import { LanguageSwitcher } from "./language-switcher";
import { ThemeToggle } from "./theme-toggle";

const iconButtonClass =
  "text-white/70 hover:bg-white/10 hover:text-white focus-visible:ring-primary focus-visible:ring-offset-ink";

export function HeaderActions() {
  const t = useTranslations();
  const router = useRouter();
  const status = useAuthStore((s) => s.status);
  const session = useAuthStore((s) => s.session);
  const [isLoggingOut, setIsLoggingOut] = React.useState(false);

  const isAuthenticated = status === "authenticated" && Boolean(session);

  async function handleLogout() {
    setIsLoggingOut(true);
    try {
      await logout();
      router.replace("/login");
      router.refresh();
    } finally {
      setIsLoggingOut(false);
    }
  }

  return (
    <div className="flex items-center gap-0.5">
      <AiChatWidget />
      <LanguageSwitcher className={iconButtonClass} />
      <ThemeToggle className={`hidden sm:inline-flex ${iconButtonClass}`} />

      <Link
        href="/cart"
        aria-label={t("nav.cart")}
        className="relative inline-flex h-9 w-9 items-center justify-center rounded-lg text-white/70 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
      >
        <ShoppingCart aria-hidden="true" className="h-4 w-4" />
        {isAuthenticated ? (
          <span className="absolute end-1 top-1 h-1.5 w-1.5 rounded-full bg-primary" />
        ) : null}
      </Link>

      {isAuthenticated ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="hidden h-9 gap-2 rounded-lg px-2 text-white/80 hover:bg-white/10 hover:text-white sm:inline-flex"
            >
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <UserRound aria-hidden="true" className="h-3.5 w-3.5" />
              </span>
              <span className="hidden max-w-[9rem] truncate text-xs font-medium xl:block">
                {session?.user.full_name}
              </span>
              <ChevronDown aria-hidden="true" className="h-3.5 w-3.5 text-white/65" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-60">
            <DropdownMenuLabel className="space-y-0.5">
              <span className="block text-[11px] font-normal uppercase tracking-wider text-muted-foreground">
                {t("auth.signedInAs")}
              </span>
              <span className="block truncate text-sm font-medium">{session?.user.email}</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/dashboard">
                <LayoutDashboard aria-hidden="true" className="me-2 h-4 w-4" />
                {t("nav.dashboard")}
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/cart">
                <ShoppingCart aria-hidden="true" className="me-2 h-4 w-4" />
                {t("nav.cart")}
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              disabled={isLoggingOut}
              onSelect={(event) => {
                event.preventDefault();
                void handleLogout();
              }}
            >
              <LogOut aria-hidden="true" className="me-2 h-4 w-4" />
              {isLoggingOut ? t("auth.logoutLoading") : t("auth.logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ) : (
        <>
          <Button
            asChild
            variant="ghost"
            className="hidden h-9 rounded-lg px-3 text-white/80 hover:bg-white/10 hover:text-white sm:inline-flex"
          >
            <Link href="/login">{t("nav.login")}</Link>
          </Button>
          <Button asChild className="hidden h-9 rounded-lg px-4 sm:inline-flex">
            <Link href="/onboarding">{t("nav.register")}</Link>
          </Button>
          <Button asChild variant="ghost" size="icon" className={`sm:hidden ${iconButtonClass}`}>
            <Link href="/login" aria-label={t("nav.login")}>
              <UserRound aria-hidden="true" className="h-4 w-4" />
            </Link>
          </Button>
        </>
      )}

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("nav.menu")}
            className={`lg:hidden ${iconButtonClass}`}
          >
            <Menu aria-hidden="true" className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64 p-2">
          <DropdownMenuItem asChild>
            <Link href="/catalog">{t("catalog.title")}</Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href="/#solucoes">{t("nav.solutions")}</Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href="/#a-forja">{t("nav.about")}</Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          {isAuthenticated ? (
            <>
              <DropdownMenuItem asChild>
                <Link href="/dashboard">{t("nav.dashboard")}</Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href="/cart">{t("nav.cart")}</Link>
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={isLoggingOut}
                onSelect={(event) => {
                  event.preventDefault();
                  void handleLogout();
                }}
              >
                <LogOut aria-hidden="true" className="me-2 h-4 w-4" />
                {isLoggingOut ? t("auth.logoutLoading") : t("auth.logout")}
              </DropdownMenuItem>
            </>
          ) : (
            <>
              <DropdownMenuItem asChild>
                <Link href="/login">{t("nav.login")}</Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href="/onboarding">{t("nav.register")}</Link>
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
