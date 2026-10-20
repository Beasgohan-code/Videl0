import "./globals.css";
import type { Metadata, Viewport } from "next";
import { IOSNav, IOSTabBar } from "@/components/ios/IOSNav";
import { StudioProvider } from "@/components/studio/StudioProvider";
import { TelegramProvider } from "@/components/TelegramProvider";

export const metadata: Metadata = {
  title: "Videl 👑 Studio",
  description: "A professional Telegram bot control panel for channel publishing, group management and live service analytics.",
  openGraph: {
    title: "Videl 👑 Studio",
    description: "Manage Videl, publish channel updates, protect groups and review live service metrics.",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Videl",
  },
  formatDetection: { telephone: false },
  other: {
    "telegram:card": "summary_large_image",
  }
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#080b1a",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen text-white antialiased">
        <TelegramProvider><StudioProvider>
          {/* iOS safe area + Telegram viewport + background */}
          <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(96,165,250,0.12),transparent_55%),radial-gradient(ellipse_at_bottom_right,_rgba(167,139,250,0.10),transparent_45%),linear-gradient(to_bottom,_rgba(8,11,26,0.5),rgba(8,11,26,0.5))]" />
          <div className="relative z-10 min-h-screen flex flex-col lg:pl-60">
            <div className="px-4 lg:px-6 pt-[env(safe-area-inset-top)]">
              <IOSNav />
            </div>
            <div className="flex-1 px-4 lg:px-6 pb-[calc(1rem+env(safe-area-inset-bottom))] md:pb-6">
              {children}
            </div>
            <IOSTabBar />
            {/* bottom spacer for iOS tab bar + Telegram safe area */}
            <div className="h-[88px] lg:hidden" />
            <div className="h-[env(safe-area-inset-bottom)]" />
          </div>
        </StudioProvider></TelegramProvider>
      </body>
    </html>
  );
}
