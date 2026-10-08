/**
 * dependency-cruiser — Forja B2B frontend architecture boundaries.
 *
 * Direcao de dependencia desejada (de cima para baixo):
 *
 *   app (Next.js routes, composition root)
 *     -> features (modulos de negocio, um por pasta)
 *     -> core/application (casos de uso + portas)
 *     -> core/domain (entidades/contratos neutros)
 *     -> infrastructure (adapters externos: HTTP, config, storage)
 *     -> shared (ui, lib, stores)
 *
 * Regras verificadas aqui:
 *  - Sem ciclos.
 *  - core/domain nao depende de application/infrastructure/shared/features/app.
 *  - core (inteiro) nao importa React/Next/TanStack/Zustand nem infrastructure.
 *  - shared/ui (componentes) nao importa core/infrastructure/features/app.
 *  - infrastructure nao importa shared/ui, app nem features.
 *  - features nao importam internals de outras features.
 */

/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: "no-circular",
      severity: "error",
      comment: "Nenhuma dependencia circular.",
      from: {},
      to: { circular: true },
    },
    {
      name: "domain-isolated",
      severity: "error",
      comment: "O dominio nao pode depender de camadas superiores.",
      from: { path: "^core/domain" },
      to: { path: "^(core/application|infrastructure|shared|features|app)" },
    },
    {
      name: "core-no-ui-frameworks",
      severity: "error",
      comment: "core deve ser independente de React/Next/TanStack/Zustand.",
      from: { path: "^core" },
      to: { path: "node_modules/(react|react-dom|next|@tanstack|zustand)(/|$)" },
    },
    {
      name: "core-no-infrastructure",
      severity: "error",
      comment: "core nao pode depender de infraestrutura (dependencia invertida).",
      from: { path: "^core" },
      to: { path: "^infrastructure" },
    },
    {
      name: "core-no-app-or-features",
      severity: "error",
      comment: "core nao pode depender de app (rotas) nem de features.",
      from: { path: "^core" },
      to: { path: "^(app|features)" },
    },
    {
      name: "ui-isolated",
      severity: "error",
      comment: "Componentes visuais nao podem depender de core/infra/features/app.",
      from: { path: "^shared/ui" },
      to: { path: "^(core|infrastructure|features|app)" },
    },
    {
      name: "infrastructure-no-ui-or-app",
      severity: "error",
      comment: "infrastructure nao pode depender de UI, rotas ou features.",
      from: { path: "^infrastructure" },
      to: { path: "^(shared/ui|app|features)" },
    },
    {
      name: "features-no-cross-internal-imports",
      severity: "error",
      comment: "Uma feature nao pode importar internals de outra feature.",
      from: { path: "^features/([^/]+)/" },
      to: {
        path: "^features/[^/]+/",
        pathNot: "^features/$1/",
      },
    },
  ],
  options: {
    doNotFollow: {
      path: "node_modules",
    },
    exclude: {
      path: "\\.next|node_modules",
    },
    tsConfig: {
      fileName: "tsconfig.json",
    },
    tsPreCompilationDeps: true,
  },
};
