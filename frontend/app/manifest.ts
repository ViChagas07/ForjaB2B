import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Forja B2B",
    short_name: "Forja",
    description: "Plataforma B2B para a indústria.",
    start_url: "/pt-BR",
    display: "standalone",
    background_color: "#0A0A0A",
    theme_color: "#F59E0B",
    icons: [
      {
        src: "/icon.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
