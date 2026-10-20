"use client";
import Link from "next/link";
import { useTelegram } from "@/components/TelegramProvider";
import { useStudio, type Section } from "@/components/studio/StudioProvider";
import { canOpenSection } from "@/lib/access";
import {
  Home,
  Palette,
  Wand2,
  MessageCircle,
  Users,
  Zap,
  BarChart3,
  Send,
  Settings2,
  ChevronRight,
  LogOut,
} from "lucide-react";
const tabs: { tab: Section; label: string; icon: typeof Home }[] = [
  { tab: "home", label: "Home", icon: Home },
  { tab: "post", label: "Post Studio", icon: Palette },
  { tab: "tools", label: "Creator Tools", icon: Wand2 },
  { tab: "chat", label: "Bot Inbox", icon: MessageCircle },
  { tab: "groups", label: "Group Manager", icon: Users },
  { tab: "automation", label: "Automation", icon: Zap },
  { tab: "analytics", label: "Analytics", icon: BarChart3 },
  { tab: "broadcast", label: "Broadcast", icon: Send },
  { tab: "settings", label: "Bot Settings", icon: Settings2 },
];
export function IOSNav() {
  const { tab } = useStudio();
  const telegram = useTelegram();
  const visible = tabs.filter((item) =>
    canOpenSection(item.tab, telegram.authenticated),
  );
  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-50 hidden w-60 flex-col border-r border-indigo-300/10 bg-[#080b1a]/95 px-4 py-7 lg:flex">
        <Link href="/" className="px-3 text-2xl font-bold">
          Videl <span className="text-indigo-300">Studio</span>
        </Link>
        <p className="mb-3 mt-10 px-3 text-[10px] uppercase tracking-[.2em] text-white/30">
          {telegram.authenticated ? "Owner workspace" : "Create & share"}
        </p>
        <nav aria-label="Main navigation" className="space-y-2">
          {visible.map((item) => (
            <Link
              key={item.tab}
              href={item.tab === "home" ? "/" : `/?tab=${item.tab}`}
              aria-current={tab === item.tab ? "page" : undefined}
              className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm ${tab === item.tab ? "bg-indigo-500/20 text-white" : "text-indigo-100/50 hover:bg-white/5"}`}
            >
              <item.icon size={18} />
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto p-3 text-xs leading-6 text-indigo-100/40">
          <p>Designed for your next idea.</p>
          <Link href="/?tab=auth" className="text-indigo-200/60">
            Owner access →
          </Link>
        </div>
      </aside>
      <header className="flex h-16 items-center justify-between border-b border-indigo-200/10">
        <div className="flex items-center gap-2 text-xs">
          <Link href="/" className="font-semibold">
            Videl Studio
          </Link>
          <ChevronRight size={12} />
          <span className="text-indigo-100/45">
            {visible.find((item) => item.tab === tab)?.label || "Owner access"}
          </span>
        </div>
        {telegram.authenticated === true ? (
          <button
            onClick={() => void telegram.logout()}
            className="ios-btn ios-btn-glass text-xs"
          >
            <LogOut size={14} /> Sign out
          </button>
        ) : (
          <Link href="/?tab=auth" className="text-xs text-indigo-200/45">
            Owner access
          </Link>
        )}
      </header>
    </>
  );
}
export function IOSTabBar() {
  const { tab, open } = useStudio();
  const { authenticated } = useTelegram();
  const visible = tabs.filter((item) =>
    canOpenSection(item.tab, authenticated),
  );
  return (
    <nav
      aria-label="Mobile navigation"
      className="fixed inset-x-0 bottom-0 z-40 overflow-x-auto border-t border-white/10 bg-[#0c1222]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
    >
      <div
        className={`mx-auto flex py-2 ${authenticated ? "w-max min-w-full" : "max-w-xl"}`}
      >
        {visible.map((item) => (
          <button
            key={item.tab}
            onClick={() => {
              open(item.tab);
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
            aria-current={tab === item.tab ? "page" : undefined}
            className={`flex flex-1 flex-col items-center gap-1 rounded-xl px-4 py-2 ${tab === item.tab ? "bg-white/5 text-indigo-100" : "text-white/40"}`}
          >
            <item.icon size={19} />
            <span className="whitespace-nowrap text-[10px]">{item.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
