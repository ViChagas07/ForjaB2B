import { CreditCard } from "lucide-react";

type PaymentMethodIconVariant = "pix" | "card";

interface PaymentMethodIconProps {
  variant: PaymentMethodIconVariant;
  className?: string;
}

/**
 * Ícones dos meios de pagamento. O Pix usa a marca oficial (diamante) em SVG
 * embutido, já que o Lucide não a oferece; o cartão reaproveita o glifo do
 * Lucide para manter o mesmo traço do restante da interface.
 */
export function PaymentMethodIcon({ variant, className }: PaymentMethodIconProps) {
  if (variant === "card") {
    return <CreditCard aria-hidden="true" className={className} />;
  }

  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M5.283 18.36a3.505 3.505 0 0 0 2.493-1.032l3.6-3.6a.684.684 0 0 1 .946 0l3.613 3.613a3.504 3.504 0 0 0 2.493 1.032h.71l-4.56 4.56a3.647 3.647 0 0 1-5.156 0L4.85 18.36ZM18.428 5.627a3.505 3.505 0 0 0-2.493 1.032l-3.613 3.614a.67.67 0 0 1-.946 0l-3.6-3.6A3.505 3.505 0 0 0 5.283 5.64h-.434l4.573-4.572a3.646 3.646 0 0 1 5.156 0l4.559 4.559ZM1.068 9.422 3.79 6.699h1.492a2.483 2.483 0 0 1 1.744.722l3.6 3.6a1.73 1.73 0 0 0 2.443 0l3.614-3.613a2.482 2.482 0 0 1 1.744-.723h1.767l2.737 2.737a3.646 3.646 0 0 1 0 5.156l-2.736 2.736h-1.768a2.482 2.482 0 0 1-1.744-.722l-3.613-3.613a1.77 1.77 0 0 0-2.444 0l-3.6 3.6a2.483 2.483 0 0 1-1.744.722H3.791l-2.723-2.723a3.646 3.646 0 0 1 0-5.156" />
    </svg>
  );
}
