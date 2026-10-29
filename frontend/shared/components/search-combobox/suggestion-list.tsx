"use client";

import { Barcode, Folder, Search, Tag } from "lucide-react";
import { useTranslations } from "next-intl";

import type { components } from "@/core/domain/api-schema";
import { displayCategoryName } from "@/shared/lib/category-display";
import { cn } from "@/shared/lib/utils";

import { HighlightMatch } from "./highlight-match";

type SuggestTerm = components["schemas"]["SuggestTermOut"];
type SuggestCategory = components["schemas"]["SuggestCategoryOut"];

interface SuggestionListProps {
  terms: SuggestTerm[];
  categories: SuggestCategory[];
  /** Trecho digitado no input (para o highlight). */
  query: string;
  /** Id do listbox (pai) para gerar ids estáveis das opções. */
  listboxId: string;
  /** Índice absoluto da primeira opção desta lista na navegação plana. */
  baseIndex: number;
  activeIndex: number | null;
  onActiveIndexChange: (index: number) => void;
  onTermSelect: (term: SuggestTerm) => void;
  onCategorySelect: (category: SuggestCategory) => void;
}

function termIcon(kind: SuggestTerm["kind"]) {
  if (kind === "brand") {
    return Tag;
  }
  if (kind === "sku") {
    return Barcode;
  }
  return Search;
}

/**
 * Coluna esquerda do dropdown: termos (com o trecho digitado em negrito) e
 * categorias no formato "em <Categoria>". As opções pertencem ao listbox do
 * painel (ids estáveis derivados do índice absoluto).
 */
export function SuggestionList({
  terms,
  categories,
  query,
  listboxId,
  baseIndex,
  activeIndex,
  onActiveIndexChange,
  onTermSelect,
  onCategorySelect,
}: SuggestionListProps) {
  const t = useTranslations();
  const hasContent = terms.length > 0 || categories.length > 0;
  if (!hasContent) {
    return null;
  }

  return (
    <li
      role="group"
      aria-label={t("search.suggestionsGroup")}
      className="min-w-0 md:col-start-1 md:row-start-1"
    >
      <ul className="divide-y divide-border/60">
        {terms.map((term, offset) => {
          const absoluteIndex = baseIndex + offset;
          const optionId = `${listboxId}-opt-${absoluteIndex}`;
          const Icon = termIcon(term.kind);
          return (
            <li
              key={`${term.kind}-${term.text}`}
              role="option"
              id={optionId}
              aria-selected={activeIndex === absoluteIndex}
              onMouseDown={(event) => event.preventDefault()}
              onMouseMove={() => onActiveIndexChange(absoluteIndex)}
              onClick={() => onTermSelect(term)}
              className={cn(
                "flex cursor-pointer items-center gap-2.5 px-4 py-2.5 text-sm",
                activeIndex === absoluteIndex
                  ? "bg-accent text-accent-foreground"
                  : "hover:bg-muted/60",
              )}
            >
              <Icon aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
              <HighlightMatch text={term.text} query={query} className="min-w-0 truncate" />
            </li>
          );
        })}
        {categories.map((category, offset) => {
          const absoluteIndex = baseIndex + terms.length + offset;
          const optionId = `${listboxId}-opt-${absoluteIndex}`;
          return (
            <li
              key={category.slug}
              role="option"
              id={optionId}
              aria-selected={activeIndex === absoluteIndex}
              onMouseDown={(event) => event.preventDefault()}
              onMouseMove={() => onActiveIndexChange(absoluteIndex)}
              onClick={() => onCategorySelect(category)}
              className={cn(
                "flex cursor-pointer items-center gap-2.5 px-4 py-2.5 text-sm",
                activeIndex === absoluteIndex
                  ? "bg-accent text-accent-foreground"
                  : "hover:bg-muted/60",
              )}
            >
              <Folder aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 truncate text-muted-foreground">
                {t("search.inCategory", { category: displayCategoryName(category.name) })}
              </span>
            </li>
          );
        })}
      </ul>
    </li>
  );
}
