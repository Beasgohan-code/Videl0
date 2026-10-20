/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async redirects() {
    return [
      ["/dashboard", "home"], ["/dashboard/channel", "post"], ["/dashboard/chat", "chat"],
      ["/post", "post"], ["/chat", "chat"], ["/groups", "groups"], ["/automation", "automation"],
      ["/analytics", "analytics"], ["/broadcast", "broadcast"], ["/settings", "settings"], ["/auth", "auth"],
    ].map(([source, tab]) => ({ source, destination: `/?tab=${tab}`, permanent: false }));
  },
  experimental: { optimizePackageImports: ["lucide-react"] },
  env: {
    NEXT_PUBLIC_BOT_USERNAME: process.env.BOT_USERNAME || process.env.NEXT_PUBLIC_BOT_USERNAME || "Videl0Bot",
  },
};
export default nextConfig;
