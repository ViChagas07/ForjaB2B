/**
 * Debounce puro (sem React): adia a execução da tarefa e cancela a pendente.
 *
 * Usado pelo hook `useDebouncedValue`; existe como função separada para ser
 * testável com fake timers (o projeto não tem renderer de testes de hooks).
 */
export type Debouncer = (task: () => void) => () => void;

export function createDebouncer(delayMs: number): Debouncer {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return (task: () => void) => {
    if (timer !== undefined) {
      clearTimeout(timer);
    }
    timer = setTimeout(() => {
      timer = undefined;
      task();
    }, delayMs);
    return () => {
      if (timer !== undefined) {
        clearTimeout(timer);
        timer = undefined;
      }
    };
  };
}
