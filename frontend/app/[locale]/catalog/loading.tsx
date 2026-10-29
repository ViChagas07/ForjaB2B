import { CatalogLoadingSkeleton } from "@/features/catalog/catalog-skeleton";
import { SiteFooter } from "@/shared/components/site-footer";
import { SiteHeader } from "@/shared/components/site-header";

export default function CatalogLoading() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="container flex-1 py-12">
        <CatalogLoadingSkeleton />
      </main>
      <SiteFooter />
    </>
  );
}
