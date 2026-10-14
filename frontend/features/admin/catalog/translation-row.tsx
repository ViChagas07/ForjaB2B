"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";
import { Badge } from "@/shared/ui/badge";

import type { ProductTranslationAdmin, TranslationUpdate } from "@/core/domain/catalog";

interface TranslationRowProps {
  translation: ProductTranslationAdmin;
  onUpdate: ({ locale, payload }: { locale: string; payload: TranslationUpdate }) => void;
  isPending: boolean;
}

export function TranslationRow({ translation, onUpdate, isPending }: TranslationRowProps) {
  const t = useTranslations("admin.catalog.products.form.translations");
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(translation.name ?? "");
  const [description, setDescription] = useState(translation.description ?? "");
  const [attributes, setAttributes] = useState<Record<string, unknown>>(translation.attributes ?? {});

  const stateLabels: Record<string, string> = {
    ausente: t("stateAusente"),
    machine: t("stateMachine"),
    reviewed: t("stateReviewed"),
    stale: t("stateStale"),
  };

  const handleSubmit = (markReviewed = false) => {
    const payload: TranslationUpdate = {
      name: name || null,
      description: description || null,
      attributes: Object.keys(attributes).length > 0 ? attributes : null,
      mark_reviewed: markReviewed,
    };
    onUpdate({ locale: translation.locale, payload });
    setIsEditing(false);
  };

  const state = translation.state;
  const isStale = translation.is_stale;

  if (!isEditing) {
    return (
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 border rounded-lg bg-card">
        <div className="flex items-center gap-3 flex-1">
          <span className="font-mono text-sm px-2 py-1 bg-muted rounded">{translation.locale}</span>
          <span className="font-medium">{translation.locale_label}</span>
          <Badge variant={state === "reviewed" ? "default" : state === "machine" ? "secondary" : state === "stale" ? "destructive" : "outline"}>
            {stateLabels[state] || state}
          </Badge>
          {isStale && (
            <Badge variant="destructive" className="text-xs">{t("staleBadge")}</Badge>
          )}
          {translation.updated_at && (
            <span className="text-xs text-muted-foreground">
              {t("lastUpdated", { date: new Date(translation.updated_at).toLocaleDateString() })}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setIsEditing(true)} disabled={isPending}>
            {t("edit")}
          </Button>
          {state !== "reviewed" && (
            <Button variant="secondary" size="sm" onClick={() => handleSubmit(true)} disabled={isPending}>
              {t("markReviewed")}
            </Button>
          )}
          {false && ( // Retraduzir automaticamente - only shown if provider configured
            <Button variant="outline" size="sm" disabled>
              {t("retranslate")}
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3 p-4 border rounded-lg bg-card">
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm px-2 py-1 bg-muted rounded">{translation.locale}</span>
        <span className="font-medium">{translation.locale_label}</span>
        <Badge variant={state === "reviewed" ? "default" : state === "machine" ? "secondary" : state === "stale" ? "destructive" : "outline"}>
          {stateLabels[state] || state}
        </Badge>
      </div>
      <div className="space-y-3">
        <div className="space-y-1">
          <Label htmlFor={`trans-name-${translation.locale}`}>{t("name")}</Label>
          <Input
            id={`trans-name-${translation.locale}`}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("namePlaceholder")}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`trans-desc-${translation.locale}`}>{t("description")}</Label>
          <Textarea
            id={`trans-desc-${translation.locale}`}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t("descriptionPlaceholder")}
            rows={3}
          />
        </div>
        {Object.keys(attributes).length > 0 && (
          <div className="space-y-1">
            <Label>{t("attributes")}</Label>
            <div className="grid gap-2 sm:grid-cols-2">
              {Object.entries(attributes).map(([key, value]) => (
                <div key={key} className="space-y-1">
                  <Label htmlFor={`trans-attr-${translation.locale}-${key}`} className="text-sm font-medium">
                    {key}
                  </Label>
                  <Input
                    id={`trans-attr-${translation.locale}-${key}`}
                    value={String(value ?? "")}
                    onChange={(e) => setAttributes(prev => ({ ...prev, [key]: e.target.value }))}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="flex gap-2 pt-2 border-t">
          <Button variant="outline" size="sm" onClick={() => setIsEditing(false)}>
            {t("cancel")}
          </Button>
          <Button variant="secondary" size="sm" onClick={() => handleSubmit(true)} disabled={isPending}>
            {t("markReviewed")}
          </Button>
          <Button size="sm" onClick={() => handleSubmit(false)} disabled={isPending}>
            {t("save")}
          </Button>
        </div>
      </div>
    </div>
  );
}