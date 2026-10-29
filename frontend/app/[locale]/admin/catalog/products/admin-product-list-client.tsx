"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { Search, ChevronLeft, ChevronRight, Edit2, Eye, EyeOff, Plus, Loader2 } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { Link } from "@/i18n/navigation";
import { formatNumber } from "@/shared/lib/money";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu";
import { Badge } from "@/shared/ui/badge";
import { Skeleton } from "@/shared/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/ui/dialog";
import { errorMessageKey } from "@/shared/lib/api-error";

import { adminCatalogApi, isVersionConflict, getFieldErrors } from "@/infrastructure/http";
import type {
  AdminProductListQuery,
  AdminProductSummary,
  AdminProductStatus,
} from "@/core/domain/catalog";

function StatusBadge({
  status,
  t,
}: {
  status: AdminProductStatus;
  t: ReturnType<typeof useTranslations>;
}) {
  const statusLabels: Record<AdminProductStatus, string> = {
    DRAFT: t("status.draft"),
    ACTIVE: t("status.active"),
    ARCHIVED: t("status.archived"),
  };

  const statusVariants: Record<
    AdminProductStatus,
    "default" | "secondary" | "destructive" | "outline"
  > = {
    DRAFT: "secondary",
    ACTIVE: "default",
    ARCHIVED: "outline",
  };

  return <Badge variant={statusVariants[status]}>{statusLabels[status]}</Badge>;
}

export function AdminProductListClient() {
  const t = useTranslations("admin.catalog.products");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const session = useAuthStore((s) => s.session);
  const status = useAuthStore((s) => s.status);
  const queryClient = useQueryClient();

  const [searchQuery, setSearchQuery] = useState(searchParams.get("q") ?? "");
  const [selectedCategory, setSelectedCategory] = useState(searchParams.get("category_id") ?? "");
  const [selectedStatus, setSelectedStatus] = useState<AdminProductStatus | "">(
    (searchParams.get("status") as AdminProductStatus) ?? "",
  );
  const [currentPage, setCurrentPage] = useState(Number(searchParams.get("page")) || 1);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [productToDelete, setProductToDelete] = useState<AdminProductSummary | null>(null);

  // Verifica se é admin
  const isAdmin = session?.user.role === "ADMIN";

  // Build query params
  const queryParams: AdminProductListQuery = {
    q: searchQuery || undefined,
    category_id: selectedCategory || undefined,
    status: selectedStatus || undefined,
    page: currentPage,
    page_size: 20,
  };

  const queryKey = ["admin", "catalog", "products", queryParams];
  const { data, isLoading, isError, error } = useQuery({
    queryKey,
    queryFn: () => adminCatalogApi.listProducts(queryParams),
  });

  const publishMutation = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      adminCatalogApi.publishProduct(id, { version }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "catalog", "products"] });
    },
    onError: (err) => {
      if (isVersionConflict(err)) {
        alert(t("versionConflict"));
        queryClient.invalidateQueries({ queryKey: ["admin", "catalog", "products"] });
      }
    },
  });

  const unpublishMutation = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) =>
      adminCatalogApi.unpublishProduct(id, { version }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "catalog", "products"] });
    },
    onError: (err) => {
      if (isVersionConflict(err)) {
        alert(t("versionConflict"));
        queryClient.invalidateQueries({ queryKey: ["admin", "catalog", "products"] });
      }
    },
  });

  if (status === "idle") {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <Card className="mx-auto w-full max-w-md">
        <CardHeader>
          <CardTitle>{t("accessDenied")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert variant="destructive">
            <AlertDescription>{t("adminOnly")}</AlertDescription>
          </Alert>
          <Button asChild className="w-full">
            <Link href="/dashboard">{t("backToDashboard")}</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    const params = new URLSearchParams(searchParams.toString());
    if (searchQuery) params.set("q", searchQuery);
    else params.delete("q");
    router.push(`${pathname}?${params.toString()}`);
  };

  const handleCategoryChange = (categoryId: string) => {
    setSelectedCategory(categoryId);
    setCurrentPage(1);
    const params = new URLSearchParams(searchParams.toString());
    if (categoryId) params.set("category_id", categoryId);
    else params.delete("category_id");
    params.set("page", "1");
    router.push(`${pathname}?${params.toString()}`);
  };

  const handleStatusChange = (statusValue: AdminProductStatus | "") => {
    setSelectedStatus(statusValue);
    setCurrentPage(1);
    const params = new URLSearchParams(searchParams.toString());
    if (statusValue) params.set("status", statusValue);
    else params.delete("status");
    params.set("page", "1");
    router.push(`${pathname}?${params.toString()}`);
  };

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", String(page));
    router.push(`${pathname}?${params.toString()}`);
  };

  const handlePublish = (product: AdminProductSummary) => {
    publishMutation.mutate({ id: product.id, version: product.version });
  };

  const handleUnpublish = (product: AdminProductSummary) => {
    unpublishMutation.mutate({ id: product.id, version: product.version });
  };

  const handleDeleteClick = (product: AdminProductSummary) => {
    setProductToDelete(product);
    setDeleteDialogOpen(true);
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("loadError")}</AlertTitle>
        <AlertDescription>{t(errorMessageKey(error as any))}</AlertDescription>
      </Alert>
    );
  }

  const products = data?.items ?? [];
  const totalPages = data?.pages ?? 1;
  const totalItems = data?.total ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button asChild>
          <Link href="/admin/catalog/products/new">
            <Plus className="mr-2 h-4 w-4" />
            {t("newProduct")}
          </Link>
        </Button>
      </div>

      {/* Filtros e busca */}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1 max-sm:w-full">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="search"
                placeholder={t("searchPlaceholder")}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex gap-2">
              <select
                value={selectedCategory}
                onChange={(e) => handleCategoryChange(e.target.value)}
                className="flex h-9 w-full max-w-xs rounded-md border border-input bg-transparent px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="">{t("allCategories")}</option>
                {data?.items
                  .flatMap((p: AdminProductSummary) => p.category)
                  .filter(Boolean)
                  .map((cat: { id: string; name: string }) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.name}
                    </option>
                  ))}
              </select>
              <select
                value={selectedStatus}
                onChange={(e) => handleStatusChange(e.target.value as AdminProductStatus | "")}
                className="flex h-9 w-full max-w-xs rounded-md border border-input bg-transparent px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="">{t("allStatuses")}</option>
                <option value="DRAFT">{t("status.draft")}</option>
                <option value="ACTIVE">{t("status.active")}</option>
                <option value="ARCHIVED">{t("status.archived")}</option>
              </select>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Tabela de produtos */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full caption-bottom text-sm">
              <thead className="[&_tr]:border-b">
                <tr className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
                  <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">
                    {t("table.name")}
                  </th>
                  <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">
                    {t("table.sku")}
                  </th>
                  <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">
                    {t("table.category")}
                  </th>
                  <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">
                    {t("table.status")}
                  </th>
                  <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">
                    {t("table.price")}
                  </th>
                  <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">
                    {t("table.stock")}
                  </th>
                  <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">
                    {t("table.updatedAt")}
                  </th>
                  <th className="h-10 px-4 text-right align-middle font-medium text-muted-foreground">
                    {t("table.actions")}
                  </th>
                </tr>
              </thead>
              <tbody className="[&_tr:last-child]:border-0">
                {products.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="h-24 text-center text-muted-foreground">
                      {t("noResults")}
                    </td>
                  </tr>
                ) : (
                  products.map((product: AdminProductSummary) => (
                    <tr key={product.id} className="border-b transition-colors hover:bg-muted/50">
                      <td className="p-4">
                        <Link
                          href={`/admin/catalog/products/${product.id}`}
                          className="font-medium hover:underline"
                        >
                          {product.name}
                        </Link>
                      </td>
                      <td className="p-4 font-mono text-sm">{product.sku}</td>
                      <td className="p-4">{product.category.name}</td>
                      <td className="p-4">
                        <StatusBadge status={product.status} t={t} />
                      </td>
                      <td className="p-4">
                        {product.base_unit_price ? (
                          <span className="font-medium">
                            {formatNumber(Number(product.base_unit_price), "pt-BR")}{" "}
                            {product.currency}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">{t("priceOnRequest")}</span>
                        )}
                      </td>
                      <td className="p-4 font-medium tabular-nums">{product.stock_quantity}</td>
                      <td className="p-4 text-sm text-muted-foreground">
                        {new Date(product.updated_at).toLocaleDateString("pt-BR")}
                      </td>
                      <td className="p-4 text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <span className="sr-only">{t("actions")}</span>
                              <ChevronLeft className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-48">
                            <DropdownMenuItem asChild>
                              <Link href={`/admin/catalog/products/${product.id}`}>
                                <Edit2 className="mr-2 h-4 w-4" />
                                {t("edit")}
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link href={`/catalog/${product.id}`} target="_blank">
                                <Eye className="mr-2 h-4 w-4" />
                                {t("viewPublic")}
                              </Link>
                            </DropdownMenuItem>
                            {product.status === "DRAFT" ? (
                              <DropdownMenuItem
                                onClick={() => handlePublish(product)}
                                disabled={publishMutation.isPending}
                              >
                                {publishMutation.isPending ? (
                                  <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    {t("publishing")}
                                  </>
                                ) : (
                                  <>
                                    <Eye className="mr-2 h-4 w-4" />
                                    {t("publish")}
                                  </>
                                )}
                              </DropdownMenuItem>
                            ) : product.status === "ACTIVE" ? (
                              <DropdownMenuItem
                                onClick={() => handleUnpublish(product)}
                                disabled={unpublishMutation.isPending}
                              >
                                {unpublishMutation.isPending ? (
                                  <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    {t("unpublishing")}
                                  </>
                                ) : (
                                  <>
                                    <EyeOff className="mr-2 h-4 w-4" />
                                    {t("unpublish")}
                                  </>
                                )}
                              </DropdownMenuItem>
                            ) : null}
                            <DropdownMenuItem
                              onClick={() => handleDeleteClick(product)}
                              className="text-destructive focus:text-destructive"
                            >
                              <span className="mr-2 h-4 w-4">🗑</span>
                              {t("delete")}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Paginação */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t px-4 py-3">
              <div className="text-sm text-muted-foreground">
                {t("pageInfo", { page: currentPage, pages: totalPages, total: totalItems })}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage <= 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                  {t("previous")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={currentPage >= totalPages}
                >
                  {t("next")}
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dialog de confirmação de exclusão */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("deleteConfirmTitle")}</DialogTitle>
            <DialogDescription>
              {t("deleteConfirmDescription", { name: productToDelete?.name ?? "" })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t("cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                /* TODO: implement delete */ setDeleteDialogOpen(false);
              }}
            >
              {t("delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
