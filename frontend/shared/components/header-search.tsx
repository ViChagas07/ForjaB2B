import { cn } from "@/shared/lib/utils";

import { SearchCombobox } from "./search-combobox/search-combobox";

interface HeaderSearchProps {
  className?: string;
  inputClassName?: string;
}

/**
 * Wrapper fino do SearchCombobox para os usos no header (desktop e mobile).
 * Mantém a assinatura anterior: o painel do dropdown vive no SearchCombobox.
 */
export function HeaderSearch({ className, inputClassName }: HeaderSearchProps) {
  return <SearchCombobox className={cn(className)} inputClassName={inputClassName} />;
}
