"use client";
import { useEffect, useRef, useState } from "react";
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
  BookOpen,
  Gamepad2,
  ChevronRight,
  LogOut,
  MoreHorizontal,
  X,
  ShieldCheck,
  Music2,
} from "lucide-react";

type NavItem = {
  tab: Section;
  label: string;
  icon: typeof Home;
  ownerOnly?: boolean;
};

const tabs: NavItem[] = [
  { tab: "home", label: "Home", icon: Home },
  { tab: "post", label: "Post Studio", icon: Palette },
  { tab: "tools", label: "Creator Tools", icon: Wand2 },
  { tab: "guide", label: "Command Guide", icon: BookOpen },
  { tab: "arcade", label: "Arcade", icon: Gamepad2 },
  { tab: "music", label: "Videl Music", icon: Music2, ownerOnly: true },
  { tab: "chat", label: "Bot Inbox", icon: MessageCircle, ownerOnly: true },
  { tab: "groups", label: "Group Manager", icon: Users, ownerOnly: true },
  { tab: "automation", label: "Automation", icon: Zap, ownerOnly: true },
  { tab: "analytics", label: "Analytics", icon: BarChart3, ownerOnly: true },
  { tab: "broadcast", label: "Broadcast", icon: Send, ownerOnly: true },
  { tab: "settings", label: "Bot Settings", icon: Settings2, ownerOnly: true },
];

const groups: { label: string; tabs: Section[] }[] = [
  { label: "Create", tabs: ["home", "post", "tools", "guide"] },
  { label: "Play", tabs: ["arcade"] },
  { label: "Listen", tabs: ["music"] },
  { label: "Operate", tabs: ["chat", "groups", "automation", "analytics", "broadcast"] },
  { label: "System", tabs: ["settings", "auth"] },
];

const primaryTabs: Section[] = ["home", "music", "post", "groups"];

type StudioTheme = "aurora" | "glacier" | "orchid" | "ember";
const studioThemes: { id: StudioTheme; name: string; hue: number; swatch: string }[] = [
  { id: "aurora", name: "Aurora", hue: 247, swatch: "#818cf8" },
  { id: "glacier", name: "Glacier", hue: 190, swatch: "#67e8f9" },
  { id: "orchid", name: "Orchid", hue: 286, swatch: "#d8b4fe" },
  { id: "ember", name: "Ember", hue: 25, swatch: "#fb923c" },
];

const ownerAccess: NavItem = {
  tab: "auth",
  label: "Owner access",
  icon: ShieldCheck,
  ownerOnly: true,
};

export function IOSNav() {
  const { tab } = useStudio();
  const telegram = useTelegram();
  const [theme, setTheme] = useState<StudioTheme>("aurora");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("videl-studio-theme") as StudioTheme | null;
      if (studioThemes.some((item) => item.id === saved)) {
        setTheme(saved as StudioTheme);
        document.documentElement.dataset.studioTheme = saved as StudioTheme;
        window.dispatchEvent(new CustomEvent("videl:studio-theme", { detail: saved }));
      }
    } catch { /* Theme preference is optional in restricted browser storage. */ }
  }, []);

  function chooseTheme(next: StudioTheme) {
    setTheme(next);
    document.documentElement.dataset.studioTheme = next;
    try { localStorage.setItem("videl-studio-theme", next); } catch { /* Keep the current session theme. */ }
    window.dispatchEvent(new CustomEvent("videl:studio-theme", { detail: next }));
  }
  const visible = tabs.filter((item) => canOpenSection(item.tab, telegram.authenticated));
  const groupOf = (section: Section) =>
    groups.find((group) => group.tabs.includes(section))?.label ??
    (section === "auth" ? "System" : "");
  return (
    <>
      <aside className="studio-sidebar fixed inset-y-0 left-0 z-50 hidden w-60 flex-col border-r border-indigo-300/10 px-4 py-7 lg:flex">
        <Link href="/" className="flex items-center gap-3 px-3 text-2xl font-bold">
          <img
            src="/videl-bot-pfp.png?v=20261028"
            alt=""
            width={42}
            height={42}
            className="h-[42px] w-[42px] rounded-full border border-indigo-300/30 object-cover shadow-[0_0_24px_rgba(129,140,248,0.18)]"
          />
          <span>Videl <span className="text-indigo-300">Studio</span></span>
        </Link>
        <p className="ios-caps mb-2 mt-8 px-3 text-[11px] text-white/30">
          {telegram.authenticated ? "Owner workspace" : "Create & share"}
        </p>
        <nav aria-label="Main navigation" className="flex-1 space-y-5 overflow-y-auto pb-4">
          {groups.map((group) => {
            const items = visible.filter((item) => group.tabs.includes(item.tab));
            if (!items.length) return null;
            return (
              <div key={group.label}>
                <p className="ios-caps px-3 pb-1.5 text-[10px] text-white/25">{group.label}</p>
                <div className="space-y-1">
                  {items.map((item) => {
                    const active = tab === item.tab;
                    return (
                      <Link
                        key={item.tab}
                        href={item.tab === "home" ? "/" : `/?tab=${item.tab}`}
                        aria-current={active ? "page" : undefined}
                        className={`ios-caps relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] transition ${
                          active
                            ? "bg-indigo-500/20 text-white"
                            : "text-indigo-100/50 hover:bg-white/5 hover:text-indigo-50"
                        }`}
                      >
                        <span
                          aria-hidden
                          className={`absolute left-0 h-5 w-[2px] rounded-full bg-indigo-300 transition-opacity ${
                            active ? "opacity-100" : "opacity-0"
                          }`}
                        />
                        <item.icon size={17} aria-hidden className={active ? "text-indigo-200" : ""} />
                        <span className="truncate">{item.label}</span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>
        <div className="border-t border-white/[0.06] px-3 pt-4 text-xs leading-6 text-indigo-100/35">
          <p>Designed for your next idea.</p>
          <Link href="/?tab=auth" className="ios-caps text-indigo-200/60">
            {telegram.authenticated ? "Owner session" : "Owner access"} →
          </Link>
        </div>
      </aside>

      <header className="studio-topbar flex h-16 items-center justify-between gap-3 border-b border-indigo-200/10">
        <div className="flex min-w-0 items-center gap-2 text-xs">
          <Link href="/" className="flex shrink-0 items-center gap-2 font-semibold">
            <img
              src="/videl-bot-pfp.png?v=20261028"
              alt=""
              width={28}
              height={28}
              className="h-7 w-7 rounded-full border border-indigo-300/30 object-cover"
            />
            <svg id="videl-studio-mark" viewBox="0 0 24 24" aria-hidden="true" className="studio-mark h-5 w-5 text-indigo-200">
              <path d="M3.5 18.5 9 5l5.5 13.5M5.2 14.2h7.6M15.8 7.2c2.9.8 4.7 2.5 4.7 4.8s-1.8 4-4.7 4.8" />
            </svg>
            Videl Studio
          </Link>
          <ChevronRight size={12} aria-hidden className="shrink-0 text-indigo-100/25" />
          <span className="ios-caps shrink-0 text-indigo-100/35">{groupOf(tab)}</span>
          <ChevronRight size={12} aria-hidden className="shrink-0 text-indigo-100/25" />
          <span className="ios-caps truncate text-indigo-100/70">
            {visible.find((item) => item.tab === tab)?.label ||
              ownerAccess.label}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <details className="studio-theme-menu">
            <summary className="studio-theme-trigger" aria-label="Choose workspace color theme" title="Workspace appearance">
              <Palette size={15} aria-hidden />
              <span className="hidden sm:inline">Theme</span>
            </summary>
            <div className="studio-theme-popover" role="group" aria-label="Workspace color theme">
              <p className="ios-caps mb-2 px-1 text-[10px] text-white/40">Workspace mood</p>
              {studioThemes.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={(event) => {
                    chooseTheme(option.id);
                    event.currentTarget.closest("details")?.removeAttribute("open");
                  }}
                  aria-pressed={theme === option.id}
                  className="studio-theme-option"
                >
                  <span aria-hidden="true" style={{ background: option.swatch }} />
                  <span>{option.name}</span>
                  {theme === option.id && <span className="ml-auto text-[10px] text-indigo-200">Active</span>}
                </button>
              ))}
              <p className="mt-2 px-1 text-[10px] leading-4 text-white/35">Saved on this device. Motion respects your system preference.</p>
            </div>
          </details>
          {telegram.authenticated === true && (
            <Link href="/?tab=post" className="ios-btn ios-btn-primary hidden text-xs sm:inline-flex">
              New post
            </Link>
          )}
          {telegram.authenticated === true ? (
            <button
              onClick={() => void telegram.logout()}
              className="ios-btn ios-btn-glass text-xs"
              aria-label="Sign out of the owner session"
            >
              <LogOut size={14} aria-hidden /> <span className="hidden sm:inline">Sign out</span>
            </button>
          ) : (
            <Link href="/?tab=auth" className="ios-caps text-indigo-200/45">
              Owner access
            </Link>
          )}
        </div>
      </header>
    </>
  );
}

export function IOSTabBar() {
  const { tab, open } = useStudio();
  const { authenticated } = useTelegram();
  const sheet = useRef<HTMLDialogElement>(null);

  const visible = tabs.filter((item) => canOpenSection(item.tab, authenticated));
  const primary = primaryTabs
    .map((key) => visible.find((item) => item.tab === key))
    .filter((item): item is NavItem => Boolean(item));
  const secondary = visible.filter((item) => !primaryTabs.includes(item.tab));

  function choose(next: Section) {
    sheet.current?.close();
    open(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <nav
      aria-label="Mobile navigation"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-[#0c1222]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
    >
      <div className="mx-auto flex max-w-xl py-2">
        {primary.map((item) => (
          <button
            key={item.tab}
            onClick={() => choose(item.tab)}
            aria-current={tab === item.tab ? "page" : undefined}
            className={`flex flex-1 flex-col items-center gap-1 rounded-xl px-2 py-2 transition ${
              tab === item.tab ? "bg-white/5 text-indigo-100" : "text-white/40"
            }`}
          >
            <item.icon size={19} aria-hidden />
            <span className="ios-caps whitespace-nowrap text-[10px]">{item.label}</span>
          </button>
        ))}
        {secondary.length > 0 && (
          <button
            onClick={() => sheet.current?.showModal()}
            aria-haspopup="dialog"
            className={`flex flex-1 flex-col items-center gap-1 rounded-xl px-2 py-2 transition ${
              secondary.some((item) => item.tab === tab)
                ? "text-indigo-100"
                : "text-white/40"
            }`}
          >
            <MoreHorizontal size={19} aria-hidden />
            <span className="ios-caps text-[10px]">More</span>
          </button>
        )}
      </div>

      <dialog
        ref={sheet}
        aria-labelledby="nav-sheet-title"
        className="nav-sheet"
        onClick={(event) => {
          if (event.target === event.currentTarget) sheet.current?.close();
        }}
      >
        <section className="rounded-2xl border border-indigo-300/20 bg-[#10172b] p-4 text-white">
          <header className="flex items-center justify-between">
            <h2 id="nav-sheet-title" className="ios-caps text-sm text-white/80">
              More workspace
            </h2>
            <button
              onClick={() => sheet.current?.close()}
              aria-label="Close navigation menu"
              className="rounded-lg p-2 text-white/50 hover:bg-white/5"
            >
              <X size={16} />
            </button>
          </header>
          <div className="mt-3 space-y-4">
            {groups.map((group) => {
              const items = secondary.filter((item) => group.tabs.includes(item.tab));
              if (!items.length) return null;
              return (
                <div key={group.label}>
                  <p className="ios-caps px-1 pb-1 text-[10px] text-white/30">{group.label}</p>
                  <div className="grid grid-cols-2 gap-2">
                    {items.map((item) => (
                      <button
                        key={item.tab}
                        onClick={() => choose(item.tab)}
                        aria-current={tab === item.tab ? "page" : undefined}
                        className={`flex items-center gap-2 rounded-xl border px-3 py-3 text-left text-xs transition ${
                          tab === item.tab
                            ? "border-indigo-300/40 bg-indigo-500/15 text-white"
                            : "border-white/10 bg-white/[0.03] text-indigo-100/70"
                        }`}
                      >
                        <item.icon size={16} />
                        <span className="ios-caps truncate">{item.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          {authenticated !== true && (
            <button
              onClick={() => choose("auth")}
              className="ios-btn ios-btn-glass mt-4 w-full text-xs"
            >
              <ShieldCheck size={14} /> Owner access
            </button>
          )}
        </section>
      </dialog>
    </nav>
  );
}
