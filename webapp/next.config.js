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
  async headers() {
    return [{
      source: "/(.*)",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Content-Security-Policy", value: "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org" },
        { key: "Permissions-Policy", value: 'camera=(), geolocation=(), microphone=(self "https://web.telegram.org"), payment=(), usb=()' },
        { key: "X-Permitted-Cross-Domain-Policies", value: "none" },
      ],
    }];
  },
  experimental: { optimizePackageImports: ["lucide-react"] },
  env: {
    NEXT_PUBLIC_BOT_USERNAME: process.env.BOT_USERNAME || process.env.NEXT_PUBLIC_BOT_USERNAME || "videlapp",
  },
};
export default nextConfig;
