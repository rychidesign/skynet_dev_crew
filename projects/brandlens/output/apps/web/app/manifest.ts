import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "BrandLens",
    short_name: "BrandLens",
    description: "GEO/AIO analytics and brand visibility platform",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#2563eb",
    icons: [],
  };
}
