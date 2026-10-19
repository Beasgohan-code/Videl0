import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Videl0 — Admin Dashboard",
  description: "Videl0 Telegram Bot Admin — aiogram 3.31 • Richgram • ShizuMusic • Full Stack",
  openGraph: { title: "Videl0", description: "Telegram Bot Admin Dashboard", images: ["https://files.catbox.moe/f084wg.png"] },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0a0a0a] text-zinc-100 antialiased">
        <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(96,165,250,0.15),transparent_60%),radial-gradient(ellipse_at_bottom_right,_rgba(167,139,250,0.12),transparent_50%)]" />
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}
