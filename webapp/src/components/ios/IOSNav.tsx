"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, LayoutDashboard, Radio, MessageCircle, Settings, Shield } from "lucide-react";

const tabs = [
  { href: "/", label: "Home", icon: Home },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/channel", label: "Studio", icon: Radio },
  { href: "/dashboard/chat", label: "Chat", icon: MessageCircle },
];

export function IOSNav() {
  const path = usePathname();
  return (
    <nav className="sticky top-0 z-40 border-b border-[var(--ios-separator)] bg-[rgba(0,0,0,0.6)] backdrop-blur-[20px] -mx-4 px-4 lg:-mx-6 lg:px-6">
      <div className="mx-auto max-w-6xl flex items-center justify-between h-[56px]">
        <Link href="/" className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-[10px] bg-white text-black flex items-center justify-center font-bold text-[14px]">◍</div>
          <div className="leading-none">
            <div className="text-[16px] font-bold tracking-[-0.02em]">Videl</div>
            <div className="text-[11px] text-[var(--ios-label-secondary)] font-medium tracking-wide">PERFECT • CYBER DARK</div>
          </div>
        </Link>
        <div className="hidden md:flex items-center gap-1 ios-tabbar">
          {tabs.map(t => {
            const active = path === t.href || (t.href !== "/" && path.startsWith(t.href));
            return (
              <Link key={t.href} href={t.href} className={`ios-tab ${active ? "active" : ""}`}>
                <t.icon size={14} /> {t.label}
              </Link>
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          <a href="https://t.me/Videl0Bot" target="_blank" className="ios-pill ios-pill-blue hidden sm:inline-flex">⬪ Open in TG</a>
          <div className="h-8 w-8 rounded-full bg-[var(--ios-fill)] flex items-center justify-center text-[12px]">◎</div>
        </div>
      </div>
    </nav>
  );
}

export function IOSTabBar() {
  const path = usePathname();
  return (
    <div className="fixed bottom-0 inset-x-0 z-40 md:hidden">
      <div className="mx-auto max-w-[420px] p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))]">
        <div className="ios-glass rounded-[28px] flex items-center justify-around p-2 shadow-[0_8px_32px_rgba(0,0,0,0.4)]">
          {tabs.map(t => {
            const active = path === t.href;
            return (
              <Link key={t.href} href={t.href} className={`flex flex-col items-center gap-1 py-2 px-4 rounded-[16px] transition ${active ? "bg-white text-black" : "text-[var(--ios-label-secondary)]"}`}>
                <t.icon size={18} strokeWidth={active ? 2.5 : 2} />
                <span className="text-[10px] font-semibold tracking-wide">{t.label}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
