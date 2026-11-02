import type { SVGProps } from "react";

export function CatalogIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d="M7.68 19.5H3.52Q3.12 19.5 3.12 19.1V1.78Q3.12 1.38 3.52 1.38H16.13Q16.53 1.38 16.53 1.78V4.44" />
      <path d="M7.68 4.44 16.53 1.38" />
      <rect x="7.68" y="4.44" width="13.12" height="18.12" rx="0.4" />
      <rect x="9.91" y="6.79" width="3.12" height="3.12" rx="0.3" />
      <rect x="9.91" y="11.97" width="3.12" height="3.12" rx="0.3" />
      <rect x="9.91" y="17.21" width="3.12" height="3.12" rx="0.3" />
      <path d="M15.32 7.44h3" />
      <path d="M15.32 9.24h3" />
      <path d="M15.32 12.65h3" />
      <path d="M15.32 14.44h3" />
      <path d="M15.32 17.85h3" />
      <path d="M15.32 19.65h3" />
    </svg>
  );
}
