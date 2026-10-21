"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Search,
  ArrowUpRight,
  X,
  Home,
  MessageCircle,
  Network,
  Palette,
  Users,
  ShieldCheck,
  BarChart3,
  Send,
  Settings,
  KeyRound,
  BookOpen,
  Command as CommandIcon,
  SearchX,
} from "lucide-react";
import { EmptyState } from "./ui";
import { useTelegram } from "@/components/TelegramProvider";
import { canOpenSection } from "@/lib/access";
import { BOT_COMMANDS } from "@/lib/commands";
import { useStudio, type Section } from "./StudioProvider";

type Tool = {
  tab: Section;
  title: string;
  description: string;
  icon: typeof Search;
};

const tools: Tool[] = [
  { tab: "home", title: "Home", description: "Your creative workspace", icon: Home },
  {
    tab: "post",
    title: "Post & image designer",
    description: "Write, format, customize images and publish",
    icon: Palette,
  },
  {
    tab: "guide",
    title: "Command guide",
    description: "Every bot command, searchable and copyable",
    icon: BookOpen,
  },
  {
    tab: "tools",
    title: "Creator tools",
    description: "Caption counter, hashtags, campaign links and Markdown",
    icon: Palette,
  },
  {
    tab: "chat",
    title: "Bot inbox",
    description: "Bot DMs, groups, photos, voice and chat settings",
    icon: MessageCircle,
  },
  {
    tab: "groups",
    title: "Group Manager",
    description: "Protections, audit history and reports",
    icon: Users,
  },
  {
    tab: "federations",
    title: "Federations",
    description: "Shared ban lists and member groups",
    icon: Network,
  },
  {
    tab: "automation",
    title: "Automation",
    description: "Quiet hours and the warning ladder",
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

type Result = {
  key: string;
  title: string;
  description: string;
  icon: typeof Search;
  badge?: string;
  run: () => void;
};

export function ToolFinder() {
  const { open } = useStudio();
  const { authenticated } = useTelegram();
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);

  const results = useMemo<Result[]>(() => {
    const needle = query.trim().toLowerCase();
    const toolMatches = tools
      .filter((tool) => canOpenSection(tool.tab, authenticated))
      .filter((tool) =>
        `${tool.title} ${tool.description}`.toLowerCase().includes(needle),
      )
      .map<Result>((tool) => ({
        key: `tool:${tool.tab}`,
        title: tool.title,
        description: tool.description,
        icon: tool.icon,
        run: () => {
          dialog.current?.close();
          open(tool.tab);
          window.scrollTo({ top: 0, behavior: "smooth" });
        },
      }));

    if (needle.replace(/^\//, "").length < 2) return toolMatches;
    const commandNeedle = needle.replace(/^\//, "");

    const commandMatches = BOT_COMMANDS.filter(
      (command) =>
        (authenticated === true || !command.owner) &&
        `${command.name} ${command.summary}`.toLowerCase().includes(commandNeedle),
    )
      .sort((a, b) => {
        const aStarts = a.name.startsWith(commandNeedle) ? 0 : 1;
        const bStarts = b.name.startsWith(commandNeedle) ? 0 : 1;
        return aStarts - bStarts || a.name.localeCompare(b.name);
      })
      .slice(0, 8)
      .map<Result>((command) => ({
        key: `cmd:${command.name}`,
        title: `/${command.name}`,
        description: command.summary,
        icon: CommandIcon,
        badge: "Command",
        run: () => {
          // A full navigation keeps the deep link shareable and lets the guide
          // read ?cmd= on mount, including from a cold Mini App launch.
          window.location.assign(`/?tab=guide&cmd=${encodeURIComponent(command.name)}`);
        },
      }));

    return [...toolMatches.slice(0, 4), ...commandMatches];
  }, [authenticated, open, query]);

  const safeIndex = Math.min(index, Math.max(0, results.length - 1));

  function show() {
    setQuery("");
    setIndex(0);
    if (!dialog.current?.open) dialog.current?.showModal();
    requestAnimationFrame(() => input.current?.focus());
  }
  function choose(result?: Result) {
    if (!result) return;
    dialog.current?.close();
    result.run();
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
        className="mb-2 mt-4 flex w-full items-center gap-3 rounded-xl border border-indigo-300/10 bg-indigo-300/[.035] px-4 py-3 text-left text-xs text-indigo-100/45 transition hover:border-indigo-300/25 hover:bg-indigo-300/[.06]"
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
        onClick={(event) => {
          if (event.target === event.currentTarget) dialog.current?.close();
        }}
      >
        <section className="rounded-2xl border border-indigo-300/20 bg-[#10172b] p-4 text-white">
          <header className="flex items-center gap-3">
            <Search size={18} className="text-indigo-300" />
            <h2 id="tool-finder-title" className="font-semibold">
              Find a tool
            </h2>
            <button
              aria-label="Close search"
              onClick={() => dialog.current?.close()}
              className="ml-auto rounded-lg p-2 hover:bg-white/5"
            >
              <X size={18} />
            </button>
          </header>
          <input
            ref={input}
            aria-label="Search workspace tools"
            placeholder="Try image, analytics, /warn…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setIndex(0);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setIndex((current) => Math.min(current + 1, results.length - 1));
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setIndex((current) => Math.max(0, current - 1));
              }
              if (event.key === "Enter") {
                event.preventDefault();
                choose(results[safeIndex]);
              }
            }}
            className="ios-input mt-4"
          />
          <p className="mt-2 text-[10px] text-white/35">
            Panels and bot commands — type <span className="mono">/</span> to narrow to
            commands.
          </p>
          <div className="mt-3 max-h-[55dvh] space-y-1 overflow-y-auto" role="listbox" aria-label="Search results">
            {results.map((result, position) => (
              <button
                key={result.key}
                role="option"
                aria-selected={safeIndex === position}
                onMouseEnter={() => setIndex(position)}
                onClick={() => choose(result)}
                className={`flex w-full items-center gap-3 rounded-xl p-3 text-left ${
                  safeIndex === position ? "bg-indigo-400/15" : "hover:bg-white/5"
                }`}
              >
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-indigo-400/10 text-indigo-300">
                  <result.icon size={19} aria-hidden />
                </span>
                <span className="min-w-0">
                  <span className="flex items-center gap-2">
                    <span className={`block truncate text-sm font-medium ${result.badge ? "mono" : ""}`}>
                      {result.title}
                    </span>
                    {result.badge && (
                      <span className="ios-caps rounded-full bg-white/[0.06] px-2 py-0.5 text-[9px] text-white/40">
                        {result.badge}
                      </span>
                    )}
                  </span>
                  <span className="mt-1 block truncate text-[11px] text-white/40">
                    {result.description}
                  </span>
                </span>
                <ArrowUpRight size={15} aria-hidden className="ml-auto shrink-0 text-white/30" />
              </button>
            ))}
            {!results.length && (
              <EmptyState
                compact
                icon={<SearchX size={18} />}
                title="No matching panel or command"
                hint="Try “post”, “analytics” or “warn”."
              />
            )}
          </div>
          <p className="mt-3 text-[10px] text-white/35">
            ↑ ↓ to choose · Enter to open · Escape to close · type “/” to search commands
          </p>
        </section>
      </dialog>
    </>
  );
}
