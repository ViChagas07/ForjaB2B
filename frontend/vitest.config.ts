import { resolve } from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // JSX no modo automatico (react-jsx): os testes .tsx nao precisam importar
  // React (o tsconfig do Next usa preserve e o vitest transformava em classic).
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: {
      "@": resolve(__dirname, "."),
    },
  },
  test: {
    environment: "node",
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    globals: false,
  },
});
