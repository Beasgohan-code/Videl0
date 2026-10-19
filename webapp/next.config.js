/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
  env: {
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    NEXT_PUBLIC_BOT_USERNAME: process.env.BOT_USERNAME || process.env.NEXT_PUBLIC_BOT_USERNAME || "Videl0Bot",
    NEXT_PUBLIC_OWNER_ID: process.env.OWNER_ID || process.env.NEXT_PUBLIC_OWNER_ID || "",
  },
};
export default nextConfig;
