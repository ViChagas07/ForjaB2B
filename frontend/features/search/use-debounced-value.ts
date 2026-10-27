"use client";

import * as React from "react";

import { createDebouncer } from "./debounce";

/** Atraso padrão do suggest (ms): equilibra latência e volume de requisições. */
export const DEFAULT_DEBOUNCE_MS = 200;

/**
 * Devolve o valor com debounce: muda de valor só depois de `delayMs` sem
 * novas mudanças. O timer é reiniciado a cada mudança (comportamento de
 * digitação) e cancelado no cleanup do efeito.
 */
export function useDebouncedValue<T>(value: T, delayMs: number = DEFAULT_DEBOUNCE_MS): T {
  const debouncer = React.useMemo(() => createDebouncer(delayMs), [delayMs]);
  const [debounced, setDebounced] = React.useState(value);

  React.useEffect(() => {
    const cancel = debouncer(() => setDebounced(value));
    return cancel;
  }, [value, debouncer]);

  return debounced;
}
