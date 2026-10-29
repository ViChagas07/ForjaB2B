"use client";

import { LockKeyhole } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";

interface AuthGateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
}

/** Convite para entrar/cadastrar a empresa antes de uma ação autenticada. */
export function AuthGateDialog({ open, onOpenChange, title, description }: AuthGateDialogProps) {
  const t = useTranslations();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md rounded-2xl">
        <DialogHeader className="space-y-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent text-accent-foreground">
            <LockKeyhole aria-hidden="true" className="h-5 w-5" />
          </span>
          <DialogTitle className="text-xl">{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-2 pt-2">
          <Button asChild size="lg" className="rounded-xl">
            <Link href="/login">{t("nav.login")}</Link>
          </Button>
          <Button asChild size="lg" variant="outline" className="rounded-xl">
            <Link href="/onboarding">{t("nav.register")}</Link>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
