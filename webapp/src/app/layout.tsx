import "./globals.css";
import type { Metadata, Viewport } from "next";
import { IOSNav, IOSTabBar } from "@/components/ios/IOSNav";

export const metadata: Metadata = {
  title: "Videl — iOS Perfect • Music • AI • Studio",
  description: "Videl0 Telegram Bot — iOS 26 native webapp • Channel Studio • Web Chat as real user • Kurigram • PyTgCalls • Richgram • Vercel",
  openGraph: {
    title: "Videl — iOS Perfect",
    description: "Channel Studio • Web Chat (owner-only, Telegram sign) • Dashboard",
    images: ["https://files.catbox.moe/f084wg.png"],
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Videl",
  },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#000000",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-black text-white antialiased">
        {/* iOS safe area + background */}
        <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(96,165,250,0.12),transparent_55%),radial-gradient(ellipse_at_bottom_right,_rgba(167,139,250,0.10),transparent_45%),linear-gradient(to_bottom,_rgba(10,10,12,1),rgba(0,0,0,1))]" />
        <div className="relative z-10 min-h-screen flex flex-col">
          <div className="px-4 lg:px-6 pt-[env(safe-area-inset-top)]">
            <IOSNav />
          </div>
          <div className="flex-1 px-4 lg:px-6 pb-[calc(1rem+env(safe-area-inset-bottom))] md:pb-6">
            {children}
          </div>
          <IOSTabBar />
          {/* bottom spacer for iOS tab bar */}
          <div className="h-[88px] md:hidden" />
        </div>
      </body>
    </html>
  );
}
