"use client";
import { useEffect, useRef, useState } from "react";
import {
  Search,
  ArrowUpRight,
  X,
  Home,
  MessageCircle,
  Palette,
  Users,
  ShieldCheck,
  BarChart3,
  Send,
  Settings,
  KeyRound,
} from "lucide-react";
import { useStudio, type Section } from "./StudioProvider";
const tools: {
  tab: Section;
  title: string;
  description: string;
  icon: typeof Search;
}[] = [
  {
    tab: "home",
    title: "Home",
    description: "Live music, group and user totals",
    icon: Home,
  },
  {
    tab: "post",
    title: "Post & image designer",
    description: "Write, format, customize images and publish",
    icon: Palette,
  },
  {
    tab: "chat",
    title: "Smart Chat",
    description: "Send messages as your bot or user session",
    icon: MessageCircle,
  },
  {
    tab: "groups",
    title: "Group Manager",
    description: "Find groups and edit protections",
    icon: Users,
  },
  {
    tab: "automation",
    title: "Automation",
    description: "Welcome messages and moderation rules",
    icon: ShieldCheck,
  },
  {
    tab: "analytics",
    title: "Analytics",
    description: "Observed command activity and CSV export",
    icon: BarChart3,
  },
  {
    tab: "broadcast",
    title: "Broadcast",
    description: "Send announcements to served recipients",
    icon: Send,
  },
  {
    tab: "settings",
    title: "Settings",
    description: "Telegram configuration and service health",
    icon: Settings,
  },
  {
    tab: "auth",
    title: "Owner sign-in",
    description: "Verify or retry your owner session",
    icon: KeyRound,
  },
];
export function ToolFinder() {
  const { open } = useStudio();
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const matches = tools.filter((t) =>
    `${t.title} ${t.description}`.toLowerCase().includes(query.toLowerCase()),
  );
  function show() {
    setQuery("");
    setIndex(0);
    if (!dialog.current?.open) dialog.current?.showModal();
    requestAnimationFrame(() => input.current?.focus());
  }
  function choose(tab: Section) {
    dialog.current?.close();
    open(tab);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (
        (event.ctrlKey || event.metaKey) &&
        event.key.toLowerCase() === "k" &&
        !target.closest("input,textarea,[contenteditable=true]")
      ) {
        event.preventDefault();
        if (dialog.current?.open) dialog.current.close();
        else show();
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  return (
    <>
      <button
        onClick={show}
        className="mb-2 mt-4 flex w-full items-center gap-3 rounded-xl border border-indigo-300/10 bg-indigo-300/[.035] px-4 py-3 text-left text-xs text-indigo-100/45"
      >
        <Search size={16} />
        <span>Find a tool or jump to a workspace…</span>
        <kbd className="ml-auto hidden rounded border border-white/10 px-2 py-1 text-[10px] sm:block">
          Ctrl / ⌘ K
        </kbd>
      </button>
      <dialog
        ref={dialog}
        aria-labelledby="tool-finder-title"
        className="tool-finder"
        onClick={(e) => {
          if (e.target === e.currentTarget) dialog.current?.close();
        }}
      >
        <section className="rounded-2xl border border-indigo-300/20 bg-[#10172b] p-4 text-white">
          <header className="flex items-center gap-3">
            <Search size={18} className="text-indigo-300" />
            <h2 id="tool-finder-title" className="font-semibold">
              Find a tool
            </h2>
            <button
              aria-label="Close tool finder"
              onClick={() => dialog.current?.close()}
              className="ml-auto rounded-lg p-2"
            >
              <X size={18} />
            </button>
          </header>
          <input
            ref={input}
            aria-label="Search workspace tools"
            placeholder="Try image, group, analytics…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setIndex(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setIndex((i) => Math.min(i + 1, matches.length - 1));
              }
              if (e.key === "ArrowUp") {
                e.preventDefault();
                setIndex((i) => Math.max(0, i - 1));
              }
              if (e.key === "Enter" && matches[index]) {
                e.preventDefault();
                choose(matches[index].tab);
              }
            }}
            className="ios-input mt-4"
          />
          <div className="mt-3 max-h-[55dvh] space-y-1 overflow-y-auto">
            {matches.map((tool, i) => (
              <button
                key={tool.tab}
                onMouseEnter={() => setIndex(i)}
                onClick={() => choose(tool.tab)}
                className={`flex w-full items-center gap-3 rounded-xl p-3 text-left ${index === i ? "bg-indigo-400/15" : "hover:bg-white/5"}`}
              >
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-indigo-400/10 text-indigo-300">
                  <tool.icon size={19} />
                </span>
                <span>
                  <span className="block text-sm font-medium">
                    {tool.title}
                  </span>
                  <span className="mt-1 block text-[11px] text-white/40">
                    {tool.description}
                  </span>
                </span>
                <ArrowUpRight
                  size={15}
                  className="ml-auto shrink-0 text-white/30"
                />
              </button>
            ))}
            {!matches.length && (
              <p className="p-5 text-sm text-white/50">
                No matching tools. Try “post” or “groups”.
              </p>
            )}
          </div>
          <p className="mt-3 text-[10px] text-white/35">
            ↑ ↓ to choose · Enter to open · Escape to close
          </p>
        </section>
      </dialog>
    </>
  );
}
