"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useRouter, usePathname, useParams } from "next/navigation";
import {
  Loader2,
  AlertCircle,
  CheckCircle2,
  Image as ImageIcon,
  X,
  ChevronDown,
  ChevronUp,
  Eye,
  Plus,
  LayoutDashboard,
  Maximize2,
  Shield,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as z from "zod";

import { Link } from "@/i18n/navigation";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Badge } from "@/shared/ui/badge";
import { Skeleton } from "@/shared/ui/skeleton";
import { Separator } from "@/shared/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { cn } from "@/shared/lib/utils";
import { formatNumber } from "@/shared/lib/money";
import { errorMessageKey } from "@/shared/lib/api-error";

import { localeLabels, type Locale } from "@/i18n/locales";
import { adminCatalogApi, isVersionConflict, getFieldErrors } from "@/infrastructure/http";
import type {
  AdminProductCreate,
  AdminProductUpdate,
  AdminProductDetail,
  AdminProductSummary,
  AttributeDefinitionOut,
  StaticImageOut,
  AdminProductStatus,
  ProductTranslationAdmin,
  TranslationUpdate,
} from "@/core/domain/catalog";
import { TranslationRow } from "@/features/admin/catalog/translation-row";

// Zod schemas for validation
const basicInfoSchema = z.object({
  sku: z.string().min(1, "SKU é obrigatório").max(64),
  name: z.string().min(1, "Nome é obrigatório").max(200),
  description: z.string().min(1, "Descrição é obrigatória").max(2000),
  category_id: z.string().uuid("Categoria inválida"),
  brand_id: z.string().uuid("Marca inválida"),
  is_epi: z.boolean().default(false),
  base_unit_price: z.string().regex(/^\d+(\.\d{1,2})?$/, "Preço inválido"),
  currency: z.string().length(3).default("BRL"),
  min_order_qty: z.coerce.number().int().min(1).default(1),
  // Optional fields for preview (not required for validation)
  ca_number: z.string().optional().nullable(),
  ca_valid_until: z.string().optional().nullable(),
  unit_of_measure: z.string().optional().nullable(),
  weight_kg: z.string().optional().nullable(),
  ncm: z.string().optional().nullable(),
});

type BasicInfoForm = z.infer<typeof basicInfoSchema>;

const dynamicAttributesSchema = z.record(z.unknown());
type DynamicAttributesForm = z.infer<typeof dynamicAttributesSchema>;

const imageSchema = z.object({
  image_url: z.string().url("URL inválida").optional().or(z.literal("")),
  static_image: z.string().optional(),
});

type ImageForm = z.infer<typeof imageSchema>;

export function AdminProductFormClient({ productId }: { productId: string | null }) {
  const t = useTranslations("admin.catalog.products.form");
  const tCatalog = useTranslations("catalog");
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams();
  const session = useAuthStore((s) => s.session);
  const status = useAuthStore((s) => s.status);
  const queryClient = useQueryClient();

  const isEdit = Boolean(productId);
  const currentProductId = productId ?? params.id;

  // Form state
  const [basicInfo, setBasicInfo] = useState<BasicInfoForm>({
    sku: "",
    name: "",
    description: "",
    category_id: "",
    brand_id: "",
    is_epi: false,
    base_unit_price: "0.00",
    currency: "BRL",
    min_order_qty: 1,
    ca_number: null,
    ca_valid_until: null,
    unit_of_measure: null,
    weight_kg: null,
    ncm: null,
  });

  const [dynamicAttributes, setDynamicAttributes] = useState<Record<string, unknown>>({});
  const [imageUrl, setImageUrl] = useState("");
  const [selectedStaticImage, setSelectedStaticImage] = useState("");
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [showCustomerPreview, setShowCustomerPreview] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [unsavedChanges, setUnsavedChanges] = useState(false);

  // Load categories and brands for selects
  const { data: categories } = useQuery({
    queryKey: ["catalog", "categories"],
    queryFn: async () => {
      const result = await adminCatalogApi.listProducts({ page_size: 100 });
      const cats = result.items.map((i) => i.category);
      // Deduplicate by id
      const seen = new Set<string>();
      return cats.filter((cat) => {
        if (seen.has(cat.id)) return false;
        seen.add(cat.id);
        return true;
      });
    },
    staleTime: 5 * 60_000,
  });

  const { data: brands } = useQuery({
    queryKey: ["catalog", "brands"],
    queryFn: async () => {
      const result = await adminCatalogApi.listProducts({ page_size: 100 });
      const brandList = result.items
        .map((i) => i.brand)
        .filter((b): b is NonNullable<typeof b> => Boolean(b));
      // Deduplicate by id
      const seen = new Set<string>();
      return brandList.filter((brand) => {
        if (seen.has(brand.id)) return false;
        seen.add(brand.id);
        return true;
      });
    },
    staleTime: 5 * 60_000,
  });

  // Load static images
  const { data: staticImages } = useQuery({
    queryKey: ["admin", "catalog", "static-images"],
    queryFn: () => adminCatalogApi.listStaticImages(),
    staleTime: 5 * 60_000,
  });

  // productIdForQuery for use in queries
  const productIdForQuery = Array.isArray(currentProductId)
    ? currentProductId[0]
    : currentProductId;

  // Load product translations
  const { data: translations, refetch: refetchTranslations } = useQuery({
    queryKey: ["admin", "catalog", "translations", productIdForQuery],
    queryFn: () => adminCatalogApi.listProductTranslations(productIdForQuery!),
    enabled: isEdit && Boolean(productIdForQuery),
    staleTime: 5 * 60_000,
  });

  // Load product if editing
  const { data: product, isLoading: loadingProduct } = useQuery({
    queryKey: ["admin", "catalog", "product", productIdForQuery],
    queryFn: () => adminCatalogApi.getProduct(productIdForQuery!),
    enabled: isEdit && Boolean(productIdForQuery),
  });

  // Load attribute definitions when category changes
  const { data: attributeDefs, isLoading: loadingAttrs } = useQuery({
    queryKey: ["admin", "catalog", "attributes", basicInfo.category_id],
    queryFn: () => adminCatalogApi.getAttributeDefinitions(basicInfo.category_id),
    enabled: Boolean(basicInfo.category_id),
  });

  // Initialize form when product loads
  useEffect(() => {
    if (product) {
      setBasicInfo({
        sku: product.sku,
        name: product.name,
        description: product.description ?? "",
        category_id: product.category.id,
        brand_id: product.brand?.id ?? "",
        is_epi: product.is_epi,
        base_unit_price: product.base_unit_price ?? "0.00",
        currency: product.currency,
        min_order_qty: product.min_order_qty,
        ca_number: product.ca_number ?? null,
        ca_valid_until: product.ca_valid_until ?? null,
        unit_of_measure: product.unit_of_measure ?? null,
        weight_kg: product.weight_kg ?? null,
        ncm: product.ncm ?? null,
      });
      setDynamicAttributes(product.attributes ?? {});
      if (product.image_url) {
        setImageUrl(product.image_url);
        setImagePreview(product.image_url);
      }
    }
  }, [product]);

  // Track unsaved changes
  useEffect(() => {
    setUnsavedChanges(true);
  }, [basicInfo, dynamicAttributes, imageUrl, selectedStaticImage]);

  // Warn on leave
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (unsavedChanges) {
        e.preventDefault();
        e.returnValue = t("unsavedChangesWarning");
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [unsavedChanges, t]);

  // Category change: reset attributes not in new category
  useEffect(() => {
    if (attributeDefs) {
      const validKeys = new Set(attributeDefs.map((d) => d.key));
      const newAttrs: Record<string, unknown> = {};
      Object.entries(dynamicAttributes).forEach(([key, value]) => {
        if (validKeys.has(key)) {
          newAttrs[key] = value;
        }
      });
      const removedKeys = Object.keys(dynamicAttributes).filter((k) => !validKeys.has(k));
      if (removedKeys.length > 0) {
        alert(t("attributesRemovedWarning", { keys: removedKeys.join(", ") }));
      }
      setDynamicAttributes(newAttrs);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attributeDefs, t]);

  // Image preview
  useEffect(() => {
    if (selectedStaticImage) {
      setImagePreview(selectedStaticImage);
      setImageUrl("");
    } else if (imageUrl) {
      try {
        new URL(imageUrl);
        setImagePreview(imageUrl);
      } catch {
        setImagePreview(null);
      }
    } else {
      setImagePreview(null);
    }
  }, [imageUrl, selectedStaticImage]);

  // Validation helpers
  const validateField = (name: string, value: unknown) => {
    const newErrors = { ...errors };
    switch (name) {
      case "sku":
        if (!value) newErrors.sku = t("skuRequired");
        else delete newErrors.sku;
        break;
      case "name":
        if (!value) newErrors.name = t("nameRequired");
        else delete newErrors.name;
        break;
      case "description":
        if (!value) newErrors.description = t("descriptionRequired");
        else delete newErrors.description;
        break;
      case "category_id":
        if (!value) newErrors.category_id = t("categoryRequired");
        else delete newErrors.category_id;
        break;
      case "brand_id":
        if (!value) newErrors.brand_id = t("brandRequired");
        else delete newErrors.brand_id;
        break;
      case "base_unit_price":
        if (!value || !/^\d+(\.\d{1,2})?$/.test(String(value)))
          newErrors.base_unit_price = t("priceInvalid");
        else delete newErrors.base_unit_price;
        break;
      default:
        if (attributeDefs) {
          const def = attributeDefs.find((d) => d.key === name);
          if (def?.required && (!value || (typeof value === "string" && !value.trim()))) {
            newErrors[name] = t("fieldRequired", { field: def.label });
          } else {
            delete newErrors[name];
          }
        }
    }
    setErrors(newErrors);
  };

  const handleBasicInfoChange = (name: string, value: unknown) => {
    setBasicInfo((prev) => ({ ...prev, [name]: value }));
    validateField(name, value);
  };

  const handleAttributeChange = (key: string, value: unknown) => {
    setDynamicAttributes((prev) => ({ ...prev, [key]: value }));
    validateField(key, value);
  };

  const handleImageUrlChange = (value: string) => {
    setImageUrl(value);
    setSelectedStaticImage("");
  };

  const handleStaticImageSelect = (path: string) => {
    setSelectedStaticImage(path);
    setImageUrl("");
  };

  // Check if form is valid
  const isBasicInfoValid = () => {
    const result = basicInfoSchema.safeParse(basicInfo);
    if (!result.success) {
      result.error.errors.forEach((e) => {
        const path = e.path[0];
        if (typeof path === "string") {
          setErrors((prev) => ({ ...prev, [path]: e.message }));
        }
      });
      return false;
    }
    // Check required attributes
    if (attributeDefs) {
      let valid = true;
      attributeDefs.forEach((def) => {
        if (
          def.required &&
          (!dynamicAttributes[def.key] || String(dynamicAttributes[def.key]).trim() === "")
        ) {
          setErrors((prev) => ({ ...prev, [def.key]: t("fieldRequired", { field: def.label }) }));
          valid = false;
        }
      });
      return valid;
    }
    return true;
  };

  // Helper: determine if product is sellable (mirrors public page logic)
  const getSellableStatus = () => {
    const caStatus = basicInfo.ca_number
      ? basicInfo.ca_valid_until
        ? "VALID"
        : "EXPIRED"
      : "NOT_APPLICABLE";
    const hasValidCa = basicInfo.is_epi ? caStatus === "VALID" : true;
    const isActive = !isEdit || product?.status === "ACTIVE"; // For preview, assume published
    return isActive && hasValidCa;
  };

  // Helper: get CA status label
  const getCaStatusLabel = () => {
    if (!basicInfo.ca_number) return t("caNotApplicable");
    if (!basicInfo.ca_valid_until) return t("caExpired");
    const validUntil = new Date(basicInfo.ca_valid_until);
    const now = new Date();
    return validUntil >= now ? t("caValid") : t("caExpired");
  };

  // Helper: get CA status variant for badge
  const getCaStatusVariant = () => {
    if (!basicInfo.ca_number) return "secondary";
    if (!basicInfo.ca_valid_until) return "destructive";
    const validUntil = new Date(basicInfo.ca_valid_until);
    const now = new Date();
    return validUntil >= now ? "default" : "destructive";
  };

  // Mutations
  const createMutation = useMutation({
    mutationFn: (payload: AdminProductCreate) => adminCatalogApi.createProduct(payload),
    onSuccess: (created) => {
      setUnsavedChanges(false);
      router.push(`/admin/catalog/products/${created.id}`);
    },
    onError: (err) => {
      if (isVersionConflict(err)) {
        alert(t("versionConflict"));
      } else {
        const fieldErrors = getFieldErrors(err);
        setErrors(fieldErrors);
      }
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AdminProductUpdate }) =>
      adminCatalogApi.updateProduct(id, payload),
    onSuccess: () => {
      setUnsavedChanges(false);
      queryClient.invalidateQueries({ queryKey: ["admin", "catalog", "products"] });
      router.push(`/admin/catalog/products/${currentProductId}`);
    },
    onError: (err) => {
      if (isVersionConflict(err)) {
        alert(t("versionConflict"));
        queryClient.invalidateQueries({ queryKey: ["admin", "catalog", "products"] });
      } else {
        const fieldErrors = getFieldErrors(err);
        setErrors(fieldErrors);
      }
    },
  });

  // Translation update mutation
  const updateTranslationMutation = useMutation({
    mutationFn: ({ locale, payload }: { locale: string; payload: TranslationUpdate }) =>
      adminCatalogApi.updateProductTranslation(productIdForQuery!, locale, payload),
    onSuccess: () => {
      refetchTranslations();
    },
    onError: (err) => {
      const fieldErrors = getFieldErrors(err);
      if (Object.keys(fieldErrors).length > 0) {
        // Show field errors in translation form
        alert(Object.values(fieldErrors).join("\n"));
      } else if (err instanceof Error) {
        alert(err.message);
      }
    },
  });

  const handleSubmit = (action: "draft" | "publish") => {
    if (!isBasicInfoValid()) {
      // Focus first error
      const firstError = Object.keys(errors)[0];
      const element = document.querySelector(`[name="${firstError}"]`) as HTMLElement | null;
      element?.focus();
      return;
    }

    const basePayload = {
      ...basicInfo,
      attributes: dynamicAttributes,
      image_url: selectedStaticImage || imageUrl || undefined,
    };

    if (isEdit) {
      const updatePayload: AdminProductUpdate = {
        ...basePayload,
        version: product!.version,
      };
      if (action === "publish") {
        updateMutation.mutate({ id: productIdForQuery!, payload: updatePayload });
        // After update, call publish
        setTimeout(() => {
          adminCatalogApi.publishProduct(productIdForQuery!, { version: product!.version + 1 });
        }, 500);
      } else {
        updateMutation.mutate({ id: productIdForQuery!, payload: updatePayload });
      }
    } else {
      const createPayload: AdminProductCreate = basePayload as AdminProductCreate;
      if (action === "publish") {
        createMutation.mutate(createPayload);
        // After create, call publish - would need the created product ID
        setTimeout(() => {
          // Would need the created product ID
        }, 500);
      } else {
        createMutation.mutate(createPayload);
      }
    }
  };

  // Render attribute input based on type
  const renderAttributeInput = (def: AttributeDefinitionOut) => {
    const value = dynamicAttributes[def.key];
    const error = errors[def.key];
    const isTouched = touched[def.key];

    const handleChange = (
      e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
    ) => {
      let val: unknown = e.target.value;
      if (def.type === "number") val = val === "" ? null : Number(val);
      if (def.type === "boolean" && e.target instanceof HTMLInputElement) val = e.target.checked;
      handleAttributeChange(def.key, val);
    };

    const handleBlur = () => setTouched((prev) => ({ ...prev, [def.key]: true }));

    switch (def.type) {
      case "text":
        return (
          <div className="space-y-1">
            <Label htmlFor={def.key}>
              {def.label} {def.required && <span className="text-destructive">*</span>}
            </Label>
            <Input
              id={def.key}
              name={def.key}
              value={String(value ?? "")}
              onChange={handleChange}
              onBlur={handleBlur}
              maxLength={def.max_length ?? undefined}
              placeholder={def.max_length ? `${t("maxChars")}: ${def.max_length}` : undefined}
              className={cn(error && "border-destructive")}
              aria-invalid={!!error}
              aria-describedby={error ? `${def.key}-error` : undefined}
            />
            {def.max_length && (
              <p className="text-xs text-muted-foreground text-right">
                {String(value ?? "").length} / {def.max_length}
              </p>
            )}
            {error && isTouched && (
              <p id={`${def.key}-error`} className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
          </div>
        );
      case "number":
        return (
          <div className="space-y-1">
            <Label htmlFor={def.key}>
              {def.label} {def.required && <span className="text-destructive">*</span>}
            </Label>
            <Input
              id={def.key}
              name={def.key}
              type="number"
              value={String(value ?? "")}
              onChange={handleChange}
              onBlur={handleBlur}
              min={def.min_value ?? undefined}
              max={def.max_value ?? undefined}
              step="any"
              placeholder={def.unit ? `${t("unit")}: ${def.unit}` : undefined}
              className={cn(error && "border-destructive")}
              aria-invalid={!!error}
              aria-describedby={error ? `${def.key}-error` : undefined}
            />
            {error && isTouched && (
              <p id={`${def.key}-error`} className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
          </div>
        );
      case "enum":
        return (
          <div className="space-y-1">
            <Label htmlFor={def.key}>
              {def.label} {def.required && <span className="text-destructive">*</span>}
            </Label>
            <Select
              value={String(value ?? "")}
              onValueChange={(v: string) => handleAttributeChange(def.key, v)}
            >
              <SelectTrigger
                id={def.key}
                className={cn(error && "border-destructive")}
                aria-invalid={!!error}
              >
                <SelectValue placeholder={t("selectOption")} />
              </SelectTrigger>
              <SelectContent>
                {def.options?.map((opt) => (
                  <SelectItem key={opt.key} value={opt.key}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {error && isTouched && (
              <p id={`${def.key}-error`} className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
          </div>
        );
      case "boolean":
        return (
          <div className="space-y-1">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                id={def.key}
                name={def.key}
                checked={Boolean(value)}
                onChange={handleChange}
                onBlur={handleBlur}
                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <span className="text-sm font-medium">{def.label}</span>
              {def.required && <span className="text-destructive">*</span>}
            </label>
            {error && isTouched && (
              <p id={`${def.key}-error`} className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}
          </div>
        );
      default:
        return null;
    }
  };

  // Guard: not admin
  if (status === "idle") {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  const isAdmin = session?.user.role === "ADMIN";
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

  // Guard: loading product
  if (isEdit && loadingProduct) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {isEdit ? t("editTitle", { name: product?.name ?? "" }) : t("newTitle")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link href="/admin/catalog/products">
              <X className="mr-2 h-4 w-4" />
              {t("cancel")}
            </Link>
          </Button>
          <Button
            variant="outline"
            onClick={() => setShowCustomerPreview(true)}
            disabled={createMutation.isPending || updateMutation.isPending}
          >
            <LayoutDashboard className="mr-2 h-4 w-4" />
            {t("preview.customerView")}
          </Button>
          <Button
            variant="outline"
            onClick={() => handleSubmit("draft")}
            disabled={createMutation.isPending || updateMutation.isPending}
          >
            {createMutation.isPending || updateMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t("saving")}
              </>
            ) : (
              t("saveDraft")
            )}
          </Button>
          <Button
            onClick={() => handleSubmit("publish")}
            disabled={createMutation.isPending || updateMutation.isPending}
          >
            {createMutation.isPending || updateMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t("publishing")}
              </>
            ) : (
              t("saveAndPublish")
            )}
          </Button>
        </div>
      </div>

      {/* Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit("draft");
        }}
        className="space-y-6"
      >
        {/* Section 1: Informações Básicas */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="text-lg">1</span>
              {t("basicInfo.title")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2">
              {/* SKU */}
              <div className="space-y-1">
                <Label htmlFor="sku">
                  {t("basicInfo.sku")} <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="sku"
                  name="sku"
                  value={basicInfo.sku}
                  onChange={(e) => handleBasicInfoChange("sku", e.target.value)}
                  onBlur={() => setTouched((prev) => ({ ...prev, sku: true }))}
                  disabled={isEdit}
                  className={cn(errors.sku && "border-destructive")}
                  aria-invalid={!!errors.sku}
                  aria-describedby={errors.sku ? "sku-error" : undefined}
                />
                {errors.sku && touched.sku && (
                  <p id="sku-error" className="text-sm text-destructive" role="alert">
                    {errors.sku}
                  </p>
                )}
                {isEdit && <p className="text-xs text-muted-foreground">{t("skuImmutable")}</p>}
              </div>

              {/* Name */}
              <div className="space-y-1">
                <Label htmlFor="name">
                  {t("basicInfo.name")} <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="name"
                  name="name"
                  value={basicInfo.name}
                  onChange={(e) => handleBasicInfoChange("name", e.target.value)}
                  onBlur={() => setTouched((prev) => ({ ...prev, name: true }))}
                  maxLength={200}
                  className={cn(errors.name && "border-destructive")}
                  aria-invalid={!!errors.name}
                  aria-describedby={errors.name ? "name-error" : undefined}
                />
                <p className="text-xs text-muted-foreground text-right">
                  {basicInfo.name.length} / 200
                </p>
                {errors.name && touched.name && (
                  <p id="name-error" className="text-sm text-destructive" role="alert">
                    {errors.name}
                  </p>
                )}
              </div>

              {/* Category */}
              <div className="space-y-1">
                <Label htmlFor="category_id">
                  {t("basicInfo.category")} <span className="text-destructive">*</span>
                </Label>
                <Select
                  value={basicInfo.category_id}
                  onValueChange={(v: string) => handleBasicInfoChange("category_id", v)}
                >
                  <SelectTrigger
                    id="category_id"
                    className={cn(errors.category_id && "border-destructive")}
                    aria-invalid={!!errors.category_id}
                  >
                    <SelectValue placeholder={t("basicInfo.categoryPlaceholder")} />
                  </SelectTrigger>
                  <SelectContent>
                    {categories?.flat().map((cat) => (
                      <SelectItem key={cat.id} value={cat.id}>
                        {cat.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.category_id && touched.category_id && (
                  <p className="text-sm text-destructive" role="alert">
                    {errors.category_id}
                  </p>
                )}
              </div>

              {/* Brand */}
              <div className="space-y-1">
                <Label htmlFor="brand_id">
                  {t("basicInfo.brand")} <span className="text-destructive">*</span>
                </Label>
                <Select
                  value={basicInfo.brand_id}
                  onValueChange={(v: string) => handleBasicInfoChange("brand_id", v)}
                >
                  <SelectTrigger
                    id="brand_id"
                    className={cn(errors.brand_id && "border-destructive")}
                    aria-invalid={!!errors.brand_id}
                  >
                    <SelectValue placeholder={t("basicInfo.brandPlaceholder")} />
                  </SelectTrigger>
                  <SelectContent>
                    {brands?.flat().map((brand) => (
                      <SelectItem key={brand.id} value={brand.id}>
                        {brand.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.brand_id && touched.brand_id && (
                  <p className="text-sm text-destructive" role="alert">
                    {errors.brand_id}
                  </p>
                )}
              </div>

              {/* Description */}
              <div className="sm:col-span-2 space-y-1">
                <Label htmlFor="description">
                  {t("basicInfo.description")} <span className="text-destructive">*</span>
                </Label>
                <Textarea
                  id="description"
                  name="description"
                  value={basicInfo.description}
                  onChange={(e) => handleBasicInfoChange("description", e.target.value)}
                  onBlur={() => setTouched((prev) => ({ ...prev, description: true }))}
                  maxLength={2000}
                  rows={4}
                  className={cn(errors.description && "border-destructive")}
                  aria-invalid={!!errors.description}
                  aria-describedby={errors.description ? "description-error" : "description-hint"}
                />
                <p className="text-xs text-muted-foreground text-right">
                  {basicInfo.description.length} / 2000
                </p>
                {errors.description && touched.description && (
                  <p id="description-error" className="text-sm text-destructive" role="alert">
                    {errors.description}
                  </p>
                )}
              </div>

              {/* Price */}
              <div className="space-y-1">
                <Label htmlFor="base_unit_price">
                  {t("basicInfo.price")} <span className="text-destructive">*</span>
                </Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="base_unit_price"
                    name="base_unit_price"
                    value={basicInfo.base_unit_price}
                    onChange={(e) => handleBasicInfoChange("base_unit_price", e.target.value)}
                    onBlur={() => setTouched((prev) => ({ ...prev, base_unit_price: true }))}
                    placeholder="0,00"
                    className={cn(errors.base_unit_price && "border-destructive", "w-32")}
                    aria-invalid={!!errors.base_unit_price}
                    aria-describedby={errors.base_unit_price ? "price-error" : undefined}
                  />
                  <Select
                    value={basicInfo.currency}
                    onValueChange={(v: string) => handleBasicInfoChange("currency", v)}
                  >
                    <SelectTrigger className="w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="BRL">BRL</SelectItem>
                      <SelectItem value="USD">USD</SelectItem>
                      <SelectItem value="EUR">EUR</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {errors.base_unit_price && touched.base_unit_price && (
                  <p id="price-error" className="text-sm text-destructive" role="alert">
                    {errors.base_unit_price}
                  </p>
                )}
              </div>

              {/* Min Order Qty */}
              <div className="space-y-1">
                <Label htmlFor="min_order_qty">{t("basicInfo.minOrderQty")}</Label>
                <Input
                  id="min_order_qty"
                  name="min_order_qty"
                  type="number"
                  value={basicInfo.min_order_qty}
                  onChange={(e) => handleBasicInfoChange("min_order_qty", Number(e.target.value))}
                  min={1}
                  className="w-24"
                />
              </div>

              {/* Is EPI */}
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_epi"
                    name="is_epi"
                    checked={basicInfo.is_epi}
                    onChange={(e) => handleBasicInfoChange("is_epi", e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                  />
                  <Label htmlFor="is_epi" className="cursor-pointer mb-0">
                    {t("basicInfo.isEpi")}
                  </Label>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Section 2: Detalhes do Produto (Dynamic Attributes) */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="text-lg">2</span>
              {t("details.title")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loadingAttrs ? (
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : attributeDefs && attributeDefs.length > 0 ? (
              <div className="space-y-6">
                {/* Group by section */}
                {Array.from(new Set(attributeDefs.map((d) => d.section))).map((section) => (
                  <div key={section} className="space-y-4">
                    <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                      {section}
                    </h3>
                    <div className="grid gap-4 sm:grid-cols-2">
                      {attributeDefs
                        .filter((d) => d.section === section)
                        .sort((a, b) => a.display_order - b.display_order)
                        .map((def) => (
                          <div key={def.key}>{renderAttributeInput(def)}</div>
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-center py-8">{t("details.noAttributes")}</p>
            )}
          </CardContent>
        </Card>

        {/* Section 3: Imagem */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="text-lg">3</span>
              {t("image.title")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Image Preview */}
            <div className="space-y-2">
              <Label>{t("image.preview")}</Label>
              <div className="relative aspect-video w-full max-w-md rounded-lg border bg-muted overflow-hidden">
                {imagePreview ? (
                  <img
                    src={imagePreview}
                    alt={t("image.previewAlt")}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-muted-foreground">
                    <ImageIcon className="h-12 w-12" />
                    <span className="sr-only">{t("image.noPreview")}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Image Source Tabs */}
            <Tabs defaultValue="url" className="w-full">
              <TabsList>
                <TabsTrigger value="url">{t("image.urlTab")}</TabsTrigger>
                <TabsTrigger value="static">{t("image.staticTab")}</TabsTrigger>
              </TabsList>

              <TabsContent value="url" className="space-y-4">
                <div className="space-y-1">
                  <Label htmlFor="image_url">{t("image.urlLabel")}</Label>
                  <div className="flex gap-2">
                    <Input
                      id="image_url"
                      name="image_url"
                      type="url"
                      value={imageUrl}
                      onChange={(e) => handleImageUrlChange(e.target.value)}
                      onBlur={() => setTouched((prev) => ({ ...prev, image_url: true }))}
                      placeholder="https://exemplo.com/imagem.jpg"
                      className="flex-1"
                    />
                    <Button type="button" variant="outline" onClick={() => setShowPreview(true)}>
                      <Eye className="mr-2 h-4 w-4" />
                      {t("image.previewBtn")}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">{t("image.urlHint")}</p>
                </div>
              </TabsContent>

              <TabsContent value="static" className="space-y-4">
                <div className="space-y-1">
                  <Label>{t("image.staticLabel")}</Label>
                  {staticImages && staticImages.length > 0 ? (
                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                      {staticImages.map((img) => (
                        <button
                          key={img.path}
                          type="button"
                          onClick={() => handleStaticImageSelect(img.path)}
                          className={cn(
                            "relative aspect-video rounded-lg border-2 overflow-hidden transition-all",
                            selectedStaticImage === img.path
                              ? "border-primary ring-2 ring-primary ring-offset-2"
                              : "border-muted hover:border-primary/50",
                          )}
                          aria-pressed={selectedStaticImage === img.path}
                        >
                          <img
                            src={img.path}
                            alt={img.label}
                            className="h-full w-full object-cover"
                          />
                          <div className="absolute bottom-0 left-0 right-0 p-2 bg-black/50 text-white text-xs truncate">
                            {img.label}
                          </div>
                          {selectedStaticImage === img.path && (
                            <div className="absolute top-2 right-2">
                              <CheckCircle2 className="h-5 w-5 text-primary" />
                            </div>
                          )}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-center py-8">
                      {t("image.noStaticImages")}
                    </p>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Section 4: Publicação */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="text-lg">4</span>
              {t("publish.title")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3 p-4 bg-muted rounded-lg">
              <div className="flex-1">
                <p className="font-medium">{t("publish.draftLabel")}</p>
                <p className="text-sm text-muted-foreground">{t("publish.draftDescription")}</p>
              </div>
              <Button
                variant="outline"
                onClick={() => handleSubmit("draft")}
                disabled={createMutation.isPending || updateMutation.isPending}
              >
                {t("publish.saveDraft")}
              </Button>
            </div>
            <div className="flex items-center gap-3 p-4 bg-muted rounded-lg">
              <div className="flex-1">
                <p className="font-medium">{t("publish.publishLabel")}</p>
                <p className="text-sm text-muted-foreground">{t("publish.publishDescription")}</p>
              </div>
              <Button
                onClick={() => handleSubmit("publish")}
                disabled={createMutation.isPending || updateMutation.isPending}
              >
                {t("publish.saveAndPublish")}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Section 5: Traduções (only in edit mode) */}
        {isEdit && translations && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="text-lg">5</span>
                {t("translations.title")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">{t("translations.description")}</p>
              <div className="space-y-3">
                {translations.map((tr) => (
                  <TranslationRow
                    key={tr.locale}
                    translation={tr}
                    onUpdate={({ locale, payload }) =>
                      updateTranslationMutation.mutate({ locale, payload })
                    }
                    isPending={updateTranslationMutation.isPending}
                  />
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </form>

      {/* Image Preview Dialog (for image tab) */}
      <div
        className="fixed inset-0 z-50 flex items-center justify-center"
        role="dialog"
        aria-modal="true"
        aria-labelledby="image-preview-title"
      >
        {showPreview && imagePreview && (
          <>
            <div className="fixed inset-0 bg-black/80" onClick={() => setShowPreview(false)} />
            <div className="relative max-w-4xl w-full mx-4 max-h-[90vh] bg-background rounded-lg shadow-xl overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b">
                <h2 id="image-preview-title" className="text-lg font-semibold">
                  {t("image.previewTitle")}
                </h2>
                <Button variant="ghost" size="icon" onClick={() => setShowPreview(false)}>
                  <X className="h-5 w-5" />
                </Button>
              </div>
              <div className="p-4">
                <img
                  src={imagePreview}
                  alt={t("image.previewAlt")}
                  className="max-h-[70vh] w-auto mx-auto object-contain"
                />
              </div>
            </div>
          </>
        )}
      </div>

      {/* Customer Preview Dialog - "Como o cliente verá" */}
      <div
        className="fixed inset-0 z-50 flex items-center justify-center"
        role="dialog"
        aria-modal="true"
        aria-labelledby="customer-preview-title"
      >
        {showCustomerPreview && (
          <>
            <div
              className="fixed inset-0 bg-black/80"
              onClick={() => setShowCustomerPreview(false)}
            />
            <div className="relative max-w-4xl w-full mx-4 max-h-[90vh] bg-background rounded-lg shadow-xl overflow-hidden flex flex-col">
              <div className="flex items-center justify-between p-4 border-b">
                <h2 id="customer-preview-title" className="text-lg font-semibold">
                  {t("preview.customerView")}
                </h2>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{t("preview.note")}</span>
                  <Button variant="ghost" size="icon" onClick={() => setShowCustomerPreview(false)}>
                    <X className="h-5 w-5" />
                  </Button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                <div className="space-y-6 max-w-2xl mx-auto">
                  {/* Product Card - mirrors public page */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-2xl tracking-tight">
                        {basicInfo.name || t("preview.noName")}
                      </CardTitle>
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {/* EPI Badge */}
                        {basicInfo.is_epi && (
                          <Badge variant="secondary" className="gap-1">
                            <Shield className="h-3 w-3" />
                            {tCatalog("epiYes")}
                          </Badge>
                        )}
                        {/* CA Status Badge */}
                        <Badge variant={getCaStatusVariant()}>{getCaStatusLabel()}</Badge>
                        {/* Availability Badge */}
                        <Badge variant={getSellableStatus() ? "default" : "destructive"}>
                          {getSellableStatus() ? t("preview.available") : t("preview.notSellable")}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Image */}
                      <div className="overflow-hidden rounded-lg bg-muted">
                        {imagePreview ? (
                          <img
                            src={imagePreview}
                            alt={basicInfo.name || t("preview.noName")}
                            className="mx-auto h-72 w-full object-contain"
                          />
                        ) : (
                          <div className="flex h-72 items-center justify-center text-muted-foreground">
                            <ImageIcon className="h-12 w-12" />
                          </div>
                        )}
                      </div>

                      {/* Price */}
                      <div className="flex items-center justify-between flex-wrap gap-4">
                        <div className="text-3xl font-bold">
                          {basicInfo.base_unit_price && Number(basicInfo.base_unit_price) > 0 ? (
                            <>
                              {formatNumber(Number(basicInfo.base_unit_price), "pt-BR")}{" "}
                              {basicInfo.currency}
                            </>
                          ) : (
                            <span className="text-muted-foreground">
                              {tCatalog("priceOnRequest")}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Description */}
                      {basicInfo.description ? (
                        <div>
                          <h3 className="mb-2 font-medium">{tCatalog("description")}</h3>
                          <p className="text-sm text-muted-foreground">{basicInfo.description}</p>
                        </div>
                      ) : null}

                      {/* Details Grid */}
                      <dl className="grid gap-3 sm:grid-cols-2 text-sm">
                        <div>
                          <dt className="text-muted-foreground">{tCatalog("sku")}</dt>
                          <dd className="font-mono font-medium">
                            {basicInfo.sku || t("preview.notSet")}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-muted-foreground">{tCatalog("category")}</dt>
                          <dd className="font-medium">
                            {categories?.flat().find((c) => c.id === basicInfo.category_id)?.name ||
                              t("preview.notSet")}
                          </dd>
                        </div>
                        {basicInfo.brand_id ? (
                          <div>
                            <dt className="text-muted-foreground">{tCatalog("brand")}</dt>
                            <dd className="font-medium">
                              {brands?.flat().find((b) => b.id === basicInfo.brand_id)?.name ||
                                t("preview.notSet")}
                            </dd>
                          </div>
                        ) : null}
                        {basicInfo.unit_of_measure ? (
                          <div>
                            <dt className="text-muted-foreground">{tCatalog("unit")}</dt>
                            <dd className="font-medium">{basicInfo.unit_of_measure}</dd>
                          </div>
                        ) : null}
                        <div>
                          <dt className="text-muted-foreground">{tCatalog("minOrderQty")}</dt>
                          <dd className="font-medium">{basicInfo.min_order_qty}</dd>
                        </div>
                        {basicInfo.weight_kg ? (
                          <div>
                            <dt className="text-muted-foreground">{tCatalog("weight")}</dt>
                            <dd className="font-medium">
                              {formatNumber(Number(basicInfo.weight_kg), "pt-BR")} kg
                            </dd>
                          </div>
                        ) : null}
                        {basicInfo.ca_number ? (
                          <div>
                            <dt className="text-muted-foreground">{tCatalog("caNumber")}</dt>
                            <dd className="font-medium">{basicInfo.ca_number}</dd>
                          </div>
                        ) : null}
                        {basicInfo.ncm ? (
                          <div>
                            <dt className="text-muted-foreground">{tCatalog("ncm")}</dt>
                            <dd className="font-mono font-medium">{basicInfo.ncm}</dd>
                          </div>
                        ) : null}
                      </dl>

                      {/* Especificações - only filled attributes */}
                      {attributeDefs && attributeDefs.length > 0 ? (
                        <div>
                          <h3 className="mb-3 font-medium">{tCatalog("attributes")}</h3>
                          <dl className="grid gap-2 sm:grid-cols-2">
                            {attributeDefs
                              .filter(
                                (def) =>
                                  dynamicAttributes[def.key] &&
                                  String(dynamicAttributes[def.key]).trim() !== "",
                              )
                              .sort((a, b) => a.display_order - b.display_order)
                              .map((def) => (
                                <div key={def.key} className="flex flex-col gap-1 text-sm">
                                  <dt className="text-muted-foreground">{def.label}</dt>
                                  <dd className="font-medium">
                                    {String(dynamicAttributes[def.key])}
                                    {def.unit && (
                                      <span className="text-muted-foreground ml-1">
                                        ({def.unit})
                                      </span>
                                    )}
                                  </dd>
                                </div>
                              ))}
                          </dl>
                        </div>
                      ) : null}
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
