"use client";

import type { AccountType } from "@/core/domain/auth";
import { Tabs, TabsList, TabsTrigger } from "@/shared/ui/tabs";

interface AccountTypeToggleProps {
  value: AccountType;
  onChange: (value: AccountType) => void;
  className?: string;
}

/**
 * Alternador CPF | CNPJ usado no login e no cadastro.
 *
 * Mantém a semântica de tablist do Radix (teclado/setas e foco visível) e
 * estiliza os triggers como um segmented control.
 */
export function AccountTypeToggle({ value, onChange, className }: AccountTypeToggleProps) {
  return (
    <Tabs
      value={value}
      onValueChange={(next) => onChange(next as AccountType)}
      className={className}
    >
      <TabsList className="grid h-12 w-full grid-cols-2 rounded-xl bg-muted p-1">
        <TabsTrigger
          value="PERSON"
          className="h-full rounded-lg text-sm font-semibold data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow"
        >
          CPF
        </TabsTrigger>
        <TabsTrigger
          value="COMPANY"
          className="h-full rounded-lg text-sm font-semibold data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow"
        >
          CNPJ
        </TabsTrigger>
      </TabsList>
    </Tabs>
  );
}
