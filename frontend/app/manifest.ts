import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Forja B2B",
    short_name: "Forja",
    description: "Plataforma B2B para a indústria.",
    start_url: "/pt-BR",
    display: "standalone",
    background_color: "#F8FAFC",
    theme_color: "#F97316",
    icons: [
      {
        src: "/brand/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
