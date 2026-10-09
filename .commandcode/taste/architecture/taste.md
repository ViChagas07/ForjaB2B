# Architecture

- Prefers the backend as the single source of truth and avoids duplicating business rules or state in the frontend (e.g., cart must not live in Zustand/localStorage). Confidence: 0.9
- Never treats client-side calculations (price, total, credit) as financial authority; the frontend only displays server-resolved values. Confidence: 0.9
- Handles monetary values safely and never trusts prices or totals sent by the client. Confidence: 0.9
- Reuses the existing stack (TanStack Query, Zustand, Zod, Tailwind/shadcn, next-intl) instead of introducing a new design system, UI library, or state architecture. Confidence: 0.9
- Converts backend errors (RFC7807) into useful messages without hiding the error code/type when needed for diagnosis. Confidence: 0.85
- Prefers a layered backend architecture (router → application/use case → domain → repository) and preserves it rather than broad refactoring. Confidence: 0.9
- Uses Decimal (never float) for money, weights, and tax values, with deterministic rounding (e.g., ROUND_HALF_UP). Confidence: 0.9
- Maintains tenant isolation / RLS on multi-tenant data. Confidence: 0.85
- Reuses existing enums/tables before creating new ones and only adds migrations when truly necessary. Confidence: 0.85
- Exposes API endpoints only when the frontend/backend workflow actually needs them (no speculative APIs). Confidence: 0.8
- Never trusts weight sent by the frontend; computes shipping weight from catalog weight × quantity on the backend. Confidence: 0.9
- Keeps tax calculation, invoice generation, and payment clearly separated (tax calculation is a pure function with no persistence or credit movement). Confidence: 0.85
- Does not invent fiscal legislation, tax rates, or compliance claims; keeps tax as an explicit deterministic simulation and documents the missing fields/contracts instead of a large schema change. Confidence: 0.85
- Does not alter approved contracts without necessity. Confidence: 0.8
