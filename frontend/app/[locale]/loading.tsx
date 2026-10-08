import { Skeleton } from "@/shared/ui/skeleton";

export default function Loading() {
  return (
    <main className="container space-y-6 py-16">
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-4 w-full max-w-md" />
      <Skeleton className="h-4 w-full max-w-sm" />
    </main>
  );
}
