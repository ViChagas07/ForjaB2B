import { Skeleton } from "@/shared/ui/skeleton";

/** Fallback compartilhado pelo Suspense da página e pelo loading.tsx. */
export function CatalogLoadingSkeleton() {
  return (
    <div aria-busy="true" className="space-y-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="w-full max-w-2xl space-y-3">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-11 w-64 max-w-full" />
          <Skeleton className="h-4 w-full max-w-xl" />
        </div>
        <Skeleton className="h-10 w-36 rounded-full" />
      </div>

      <div className="grid gap-4 rounded-2xl border border-border bg-card p-5 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-10 w-full" />
        ))}
      </div>

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <Skeleton key={index} className="h-[420px] w-full rounded-2xl" />
        ))}
      </div>

      <Skeleton className="h-16 w-full rounded-2xl" />
    </div>
  );
}
