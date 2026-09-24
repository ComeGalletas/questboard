import type { NextConfig } from "next";

// Static export: the same build is served by Vercel (PWA) and bundled into the Tauri shell,
// so there is no server runtime. Auth and data go straight to Supabase from the client.
const config: NextConfig = {
  output: "export",
  reactStrictMode: true,
  images: { unoptimized: true },
  transpilePackages: ["@questboard/schema"],
};

export default config;
