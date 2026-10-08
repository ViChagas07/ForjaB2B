import type { Config } from "tailwindcss";

/**
 * Design tokens — Forja B2B (fonte central de cor).
 *
 * Valores oficiais do MEGA-PROMPT (hex), expressos em HSL para permitir
 * dark mode via CSS variables (padrao shadcn/ui) sem espalhar hex pelo codigo.
 *
 *   forge-500 #F97316   -> 24.6 95% 53.1%
 *   forge-600 #EA580C   -> 21.7 92.5% 48.2%
 *   steel-800 #1E293B   -> 217.2 32.6% 17.5%
 *   steel-900 #0F172A   -> 222.2 47.4% 11.2%
 *   platinum-50 #F8FAFC -> 210 40% 96.1%
 *   platinum-200 #E2E8F0 -> 214.3 31.8% 91.4%
 *
 * A fonte de verdade em runtime sao as CSS custom properties em globals.css;
 * esta config apenas referencia aquelas variaveis (hsl(var(--x))).
 */

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./core/**/*.{ts,tsx}",
    "./features/**/*.{ts,tsx}",
    "./infrastructure/**/*.{ts,tsx}",
    "./shared/**/*.{ts,tsx}",
    "./i18n/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "1.5rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "Noto Sans",
          "Noto Sans CJK SC",
          "Noto Sans JP",
          "Noto Sans KR",
          "Noto Sans Arabic",
          "sans-serif",
          "Apple Color Emoji",
          "Segoe UI Emoji",
        ],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
        },
        info: {
          DEFAULT: "hsl(var(--info))",
          foreground: "hsl(var(--info-foreground))",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
        },
        danger: {
          DEFAULT: "hsl(var(--danger))",
          foreground: "hsl(var(--danger-foreground))",
        },
        // Tokens de marca (acesso direto, para uso pontual).
        forge: {
          500: "#F97316",
          600: "#EA580C",
        },
        steel: {
          800: "#1E293B",
          900: "#0F172A",
        },
        platinum: {
          50: "#F8FAFC",
          200: "#E2E8F0",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
