import * as React from "react";
import { Check } from "lucide-react";

import { cn } from "@/shared/lib/utils";

/**
 * Checkbox acessível sem dependência adicional: input nativo (semântica e
 * teclado garantidos) posicionado sobre a caixa visual — o clique cai no
 * próprio input; a borda e o visto reagem a `peer-checked`/`peer-focus-visible`.
 */
const Checkbox = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <span className="relative inline-flex h-5 w-5 shrink-0 items-center justify-center">
      <input
        ref={ref}
        type="checkbox"
        className={cn(
          "peer absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0",
          className,
        )}
        {...props}
      />
      <span
        aria-hidden="true"
        className="absolute inset-0 rounded border border-input bg-background transition-colors peer-checked:border-primary peer-checked:bg-primary peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-background peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
      />
      <Check
        aria-hidden="true"
        className="relative h-3.5 w-3.5 text-primary-foreground opacity-0 transition-opacity peer-checked:opacity-100"
      />
    </span>
  ),
);
Checkbox.displayName = "Checkbox";

export { Checkbox };
