import type { Config } from "tailwindcss";

/**
 * Design tokens — Forja B2B (fonte central de cor).
 *
 * Paleta da marca: preto profundo, âmbar e branco quente. Os valores são
 * expressos em HSL para permitir dark mode via CSS variables (padrão
 * shadcn/ui) sem espalhar hex pelo código.
 *
 *   forge-500 #F59E0B   -> 38 92% 50%
 *   forge-600 #D97706   -> 32 95% 44%
 *   steel-800 #171717   -> 0 0% 9%
 *   steel-900 #0A0A0A   -> 0 0% 4%
 *   platinum-50 #FAF9F6 -> 40 20% 98%
 *   platinum-200 #F4F2ED -> 40 18% 95%
 *
 * A fonte de verdade em runtime são as CSS custom properties em globals.css;
 * esta config apenas referencia aquelas variáveis (hsl(var(--x))).
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
          100: "#FEF3C7",
          300: "#FCD34D",
          500: "#F59E0B",
          600: "#D97706",
          700: "#B45309",
        },
        ink: {
          DEFAULT: "#0A0A0A",
          soft: "#171717",
          800: "#262626",
        },
        steel: {
          800: "#171717",
          900: "#0A0A0A",
        },
        platinum: {
          50: "#FAF9F6",
          200: "#F4F2ED",
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
        rise: {
          from: { opacity: "0", transform: "translateY(18px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        rise: "rise 0.7s cubic-bezier(0.22, 1, 0.36, 1) both",
        "fade-in": "fade-in 0.5s ease-out both",
        "pulse-soft": "pulse-soft 2.6s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
