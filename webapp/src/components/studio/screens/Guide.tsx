"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  BookOpen,
  Check,
  Copy,
  Crown,
  Link2,
  ExternalLink,
  Lock,
  Music4,
  Search,
  ShieldCheck,
  Users,
  Wrench,
} from "lucide-react";
import { useTelegram } from "@/components/TelegramProvider";
import {
  BOT_COMMANDS,
  COMMAND_CATEGORIES,
  COMMAND_CONTEXTS,
  COMMAND_COUNT,
  type BotCommand,
  type CommandCategory,
} from "@/lib/commands";
import { Callout, EmptyState, PageHeader } from "../ui";

const ICONS: Record<CommandCategory, typeof BookOpen> = {
  manage: ShieldCheck,
  music: Music4,
  tools: Wrench,
  owner: Crown,
};

const ORDER: CommandCategory[] = ["manage", "music", "tools", "owner"];

const QUICK_STARTS = [
  { title: "Listen together", detail: "Start a group voice chat, then request a song.", command: "play", category: "music" as const },
  { title: "Protect links", detail: "Turn on the link lock, then review group locks.", command: "lock", category: "manage" as const },
  { title: "Welcome members", detail: "Set a greeting and enable welcome messages.", command: "setwelcome", category: "manage" as const },
];

function openExternalTelegram(event: { preventDefault: () => void; currentTarget: { href: string } }) {
  const webApp = (window as Window & {
    Telegram?: { WebApp?: { openLink?: (href: string, options?: { try_instant_view?: boolean }) => void } };
  }).Telegram?.WebApp;
  if (webApp?.openLink) {
    event.preventDefault();
    webApp.openLink(event.currentTarget.href, { try_instant_view: false });
  }
}

function copyText(value: string) {
  const command = value.split(" · ")[0];
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(command);
  const field = document.createElement("textarea");
  field.value = command;
  field.setAttribute("readonly", "");
  field.style.position = "fixed";
  field.style.opacity = "0";
  document.body.appendChild(field);
  field.select();
  document.execCommand("copy");
  field.remove();
  return Promise.resolve();
}

export default function Guide() {
  const { authenticated } = useTelegram();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<CommandCategory | "all">("all");
  const [copied, setCopied] = useState("");
  const [linked, setLinked] = useState("");
  const [focused, setFocused] = useState("");
  const search = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const target = new URLSearchParams(window.location.search).get("cmd");
    if (!target) return;
    const clean = target.replace(/^\//, "");
    setQuery(clean);
    setFocused(clean);
  }, []);

  useEffect(() => {
    if (!focused) return;
    const row = document.getElementById(`command-${focused}`);
    row?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [focused]);

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if (event.key !== "/" || event.metaKey || event.ctrlKey) return;
      const target = event.target as HTMLElement | null;
      if (target && /input|textarea|select/i.test(target.tagName)) return;
      event.preventDefault();
      search.current?.focus();
    }
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);

  const available = useMemo(
    () => BOT_COMMANDS.filter((command) => authenticated === true || !command.owner),
    [authenticated],
  );

  const counts = useMemo(() => {
    const result = { all: available.length } as Record<CommandCategory | "all", number>;
    for (const key of ORDER) result[key] = available.filter((item) => item.category === key).length;
    return result;
  }, [available]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return available.filter(
      (command) =>
        (category === "all" || command.category === category) &&
        (!needle ||
          `${command.name} ${command.usage} ${command.summary}`
            .toLowerCase()
            .includes(needle)),
    );
  }, [available, category, query]);

  const groups = ORDER.filter((key) => counts[key] > 0)
    .map((key) => ({
      key,
      label: COMMAND_CATEGORIES[key],
      commands: visible.filter((command) => command.category === key),
    }))
    .filter((group) => group.commands.length > 0);

  function copy(command: BotCommand) {
    void copyText(command.usage);
    setCopied(command.name);
    window.setTimeout(() => setCopied((value) => (value === command.name ? "" : value)), 1600);
  }

  function share(command: BotCommand) {
    const url = `${window.location.origin}/?tab=guide&cmd=${command.name}`;
    void navigator.clipboard?.writeText(url);
    setLinked(command.name);
    window.setTimeout(() => setLinked((value) => (value === command.name ? "" : value)), 1600);
  }

  const bot = (process.env.NEXT_PUBLIC_BOT_USERNAME || "videlapp").replace(/^@/, "");

  return (
    <main className="ios-page ios-page-narrow">
      <PageHeader
        eyebrow="Command guide"
        title="Everything the bot can do."
        subtitle={`All ${COMMAND_COUNT} commands the bot registers, grouped by what they are for. Type the command in Telegram — a group command replies in the group, a tool works in any chat. ${authenticated === true ? "Owner operations are included because this session is signed in." : "Owner operations stay hidden until you sign in."}`}
        actions={
          <>
            <a href={`https://t.me/${bot}?startgroup=true`} target="_blank" rel="noreferrer" onClick={openExternalTelegram} className="ios-btn ios-btn-primary text-sm">
              <Users size={15} aria-hidden /> Add to a group <ExternalLink size={15} aria-hidden />
            </a>
            <a href={`https://t.me/${bot}`} target="_blank" rel="noreferrer" onClick={openExternalTelegram} className="ios-btn ios-btn-glass text-sm">
              Open @{bot} <ExternalLink size={15} aria-hidden />
            </a>
            <span className="ios-caps text-[11px] text-[var(--ios-label-tertiary)]">/start · /help · /commands</span>
          </>
        }
      />

      <div className="sticky top-0 z-20 -mx-1 mt-8 bg-[var(--ios-bg)]/90 px-1 py-3 backdrop-blur-xl">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="relative flex-1">
            <Search size={16} className="pointer-events-none absolute left-4 top-3.5 text-[var(--ios-label-tertiary)]" />
            <input
              ref={search}
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search commands, e.g. warn, remind, lock…"
              aria-label="Search commands"
              className="ios-input !pl-11"
            />
          </label>
          <p className="ios-caps shrink-0 text-[11px] text-[var(--ios-label-tertiary)]">
            {visible.length} of {available.length} shown
          </p>
        </div>
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Command categories">
          <button
            role="tab"
            aria-selected={category === "all"}
            onClick={() => setCategory("all")}
            className={`ios-chip ${category === "all" ? "ios-chip-active" : ""}`}
          >
            All <span className="mono text-[10px] opacity-60">{counts.all}</span>
          </button>
          {ORDER.filter((key) => counts[key] > 0).map((key) => {
            const Icon = ICONS[key];
            return (
              <button
                key={key}
                role="tab"
                aria-selected={category === key}
                onClick={() => setCategory(key)}
                className={`ios-chip ${category === key ? "ios-chip-active" : ""}`}
              >
                <Icon size={13} /> {COMMAND_CATEGORIES[key]}
                <span className="mono text-[10px] opacity-60">{counts[key]}</span>
              </button>
            );
          })}
        </div>
      </div>

      <section className="ios-card mt-4 p-4 sm:p-5" aria-labelledby="guide-quick-starts">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <p className="ios-caps text-[10px] text-indigo-200/60">Quick workflows</p>
            <h2 id="guide-quick-starts" className="mt-1 text-base font-semibold text-white">Get started in a few taps</h2>
          </div>
          <span className="text-xs text-[var(--ios-label-tertiary)]">Choose a recipe to filter its commands</span>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          {QUICK_STARTS.map((workflow) => {
            const Icon = ICONS[workflow.category];
            return (
              <button
                key={workflow.command}
                type="button"
                onClick={() => {
                  setCategory(workflow.category);
                  setQuery(workflow.command);
                }}
                className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-3 text-left transition hover:border-indigo-300/25 hover:bg-indigo-300/[0.06]"
              >
                <span className="flex items-center gap-2 text-sm font-medium text-white/90"><Icon size={15} className="text-indigo-200" />{workflow.title}</span>
                <span className="mt-1.5 block text-xs leading-5 text-[var(--ios-label-secondary)]">{workflow.detail}</span>
                <code className="mono mt-2 inline-block text-[11px] text-indigo-200">/{workflow.command}</code>
              </button>
            );
          })}
        </div>
      </section>

      {!authenticated && (
        <Callout tone="info" className="mt-4" icon={<Lock size={16} aria-hidden />}>
          Owner commands are not listed publicly. Sign in with the owner Telegram account to see
          broadcasts, blocklists and watchdog controls here.
        </Callout>
      )}

      {groups.map((group) => {
        const Icon = ICONS[group.key];
        return (
          <section key={group.key} className="mt-8" aria-labelledby={`guide-${group.key}`}>
            <div className="flex items-center gap-3">
              <Icon size={17} className="text-indigo-300" />
              <h2 id={`guide-${group.key}`} className="ios-caps text-sm text-white/80">
                {group.label}
              </h2>
              <span className="h-px flex-1 bg-white/[0.07]" />
              <span className="mono text-[10px] text-[var(--ios-label-tertiary)]">
                {group.commands.length}
              </span>
            </div>
            <ul className="ios-card mt-3 divide-y divide-white/[0.055] overflow-hidden">
              {group.commands.map((command) => (
                <li
                  key={command.name}
                  id={`command-${command.name}`}
                  className={`group flex scroll-mt-40 items-start gap-3 px-4 py-3.5 sm:px-5 ${
                    focused === command.name ? "bg-indigo-400/[0.07]" : ""
                  }`}
                >
                  <code className="mono mt-0.5 shrink-0 rounded-md bg-white/[0.05] px-2 py-1 text-[12px] text-indigo-200">
                    /{command.name}
                  </code>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm leading-5 text-white/85">{command.summary}</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span className="ios-caps text-[10px] text-[var(--ios-label-tertiary)]">
                        {COMMAND_CONTEXTS[command.context]}
                      </span>
                      {command.usage !== `/${command.name}` && (
                        <span className="mono truncate text-[10px] text-[var(--ios-label-tertiary)]/80">
                          {command.usage}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="mt-0.5 flex shrink-0 items-center">
                    <button
                      onClick={() => copy(command)}
                      aria-label={`Copy /${command.name}`}
                      title={`Copy /${command.name}`}
                      className="rounded-lg p-2 text-[var(--ios-label-tertiary)] transition hover:bg-white/[0.06] hover:text-white"
                    >
                      {copied === command.name ? (
                        <Check size={15} className="text-[#30d158]" />
                      ) : (
                        <Copy size={15} />
                      )}
                    </button>
                    <button
                      onClick={() => share(command)}
                      aria-label={`Copy a link to /${command.name}`}
                      title="Copy link to this command"
                      className="rounded-lg p-2 text-[var(--ios-label-tertiary)] transition hover:bg-white/[0.06] hover:text-white"
                    >
                      {linked === command.name ? (
                        <Check size={15} className="text-[#30d158]" />
                      ) : (
                        <Link2 size={15} />
                      )}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        );
      })}

      {!groups.length && (
        <EmptyState
          className="mt-8"
          icon={<Search size={22} />}
          title={`No command matches “${query}”.`}
          hint="Try a shorter word, or send /help to the bot."
          action={
            <button
              onClick={() => {
                setQuery("");
                setCategory("all");
              }}
              className="ios-btn ios-btn-glass text-xs"
            >
              Clear filters
            </button>
          }
        />
      )}

      <footer className="mt-10 rounded-2xl border border-white/[0.08] bg-white/[0.02] p-5 text-xs leading-6 text-[var(--ios-label-secondary)]">
        <p className="ios-caps text-[10px] text-[var(--ios-label-tertiary)]">How permissions work</p>
        <ul className="mt-3 grid gap-1.5 sm:grid-cols-2">
          <li>Group commands act on the group they are sent in.</li>
          <li>Admin commands need the matching administrator right.</li>
          <li>Owner commands only answer the owner account.</li>
          <li>Tap any row to copy the exact command.</li>
        </ul>
        <p className="mt-4 text-[11px] leading-5 text-[var(--ios-label-tertiary)]">
          This list is generated from the bot&apos;s registered handlers, so it cannot promise a
          command that does not exist. Press <kbd className="mono rounded bg-white/10 px-1">/</kbd>{" "}
          anywhere to search.
        </p>
      </footer>
    </main>
  );
}
