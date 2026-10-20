"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCheck,
  MessageCircle,
  Send,
  ShieldCheck,
  UserRound,
  Search,
  Users,
  LoaderCircle,
  Trash2,
} from "lucide-react";

type Delivery = {
  key: string;
  id?: number | string;
  chatId: string;
  title: string;
  via: string;
  text: string;
  time: string;
  status: "sending" | "sent" | "failed";
  error?: string;
};
type Group = {
  id: number;
  title: string;
  members: number | null;
  available: boolean;
};
export default function SmartChat() {
  const [chatId, setChatId] = useState("");
  const [text, setText] = useState("");
  const [asUser, setAsUser] = useState(false);
  const [userAvailable, setUserAvailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const sending = useRef(false);
  const [error, setError] = useState("");
  const [groupsError, setGroupsError] = useState("");
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const end = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const load = useCallback(async () => {
    setLoading(true);
    setGroupsError("");
    void fetch("/api/stats", {
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
    })
      .then(async (response) => {
        const data = await response.json();
        setUserAvailable(
          response.ok && Boolean(data.stats?.services?.user_session),
        );
      })
      .catch(() => setUserAvailable(false));
    try {
      const response = await fetch("/api/groups", {
        cache: "no-store",
        signal: AbortSignal.timeout(12000),
      });
      const data = await response.json();
      if (!response.ok || !data.ok)
        throw new Error(data.error || "Groups unavailable");
      setGroups(data.chats || []);
      if (data.truncated)
        setGroupsError(
          "Showing the first 25 groups. Enter any additional destination manually.",
        );
    } catch (error) {
      setGroupsError(
        error instanceof Error ? error.message : "Groups could not be loaded",
      );
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [deliveries]);
  const target = groups.find((g) => String(g.id) === chatId);
  const title = target?.title || chatId || "Choose a conversation";
  const visible = deliveries.filter((d) => d.chatId === chatId);
  const filtered = groups.filter((g) =>
    `${g.title} ${g.id}`.toLowerCase().includes(query.toLowerCase()),
  );
  function select(id: string) {
    if (sending.current) return;
    setChatId(id);
    setError("");
  }
  async function send() {
    if (sending.current) return;
    const message = text.trim(),
      destination = chatId.trim(),
      via = asUser ? "user" : "bot";
    if (!destination || !message) return;
    if (asUser && !userAvailable) {
      setError("The user session is not configured.");
      return;
    }
    const key = crypto.randomUUID();
    const snapshot = text;
    sending.current = true;
    setBusy(true);
    setError("");
    const delivery: Delivery = {
      key,
      chatId: destination,
      title,
      via,
      text: message,
      time: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      status: "sending",
    };
    setDeliveries((all) => [...all, delivery].slice(-100));
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: destination,
          text: message,
          as_user: asUser,
        }),
        signal: AbortSignal.timeout(25000),
      });
      const data = await response.json();
      if (!response.ok || !data.ok)
        throw new Error(data.error || "Telegram rejected the message");
      setDeliveries((all) =>
        all.map((d) =>
          d.key === key
            ? {
                ...d,
                status: "sent",
                id: data.message_id,
                via: data.via || via,
              }
            : d,
        ),
      );
      // Preserve anything typed while Telegram was processing this message.
      setText((current) => (current === snapshot ? "" : current));
    } catch (e) {
      const reason =
        e instanceof Error ? e.message : "Delivery could not be confirmed";
      setError(reason);
      setDeliveries((all) =>
        all.map((d) =>
          d.key === key ? { ...d, status: "failed", error: reason } : d,
        ),
      );
    } finally {
      sending.current = false;
      setBusy(false);
      composer.current?.focus();
    }
  }
  return (
    <main className="mx-auto max-w-7xl py-6 sm:py-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="ios-caption2">
            VIDEL · YOUR COMMUNITY, ONE CONVERSATION AT A TIME
          </p>
          <h1 className="mt-2 ios-title">Smart Chat</h1>
          <p className="mt-2 ios-subheadline">
            A calmer place to connect. Choose a group, write your message, make
            it happen.
          </p>
        </div>
        <span className="ios-pill">
          <ShieldCheck size={13} /> Owner workspace
        </span>
      </header>
      <section className="mt-6 grid items-start gap-4 lg:grid-cols-[290px_minmax(0,1fr)]">
        <aside className="ios-card overflow-hidden">
          <div className="border-b border-indigo-300/10 p-4">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <MessageCircle size={17} className="text-indigo-300" />{" "}
              Conversations
            </h2>
            <label className="relative mt-4 block">
              <Search
                size={15}
                className="absolute left-3 top-3.5 text-indigo-200/35"
              />
              <input
                aria-label="Search groups"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="ios-input !pl-9 text-xs"
                placeholder="Search groups or chat IDs…"
              />
            </label>
          </div>
          <div className="max-h-56 space-y-1 overflow-y-auto p-2 lg:max-h-[380px]">
            {loading ? (
              <p role="status" className="p-4 text-xs text-indigo-200/50">
                Loading your groups…
              </p>
            ) : filtered.length ? (
              filtered.map((g, i) => (
                <button
                  key={g.id}
                  disabled={busy}
                  onClick={() => select(String(g.id))}
                  className={`flex w-full items-center gap-3 rounded-xl border p-3 text-left transition disabled:opacity-50 ${String(g.id) === chatId ? "border-indigo-400/30 bg-indigo-500/15" : "border-transparent hover:bg-indigo-400/5"}`}
                >
                  <span
                    className={`grid h-10 w-10 shrink-0 place-items-center rounded-full bg-gradient-to-br ${i % 2 ? "from-fuchsia-500/25 to-violet-600/20" : "from-blue-500/25 to-cyan-500/15"} text-sm font-semibold text-indigo-200`}
                  >
                    {g.title?.slice(0, 2).toUpperCase() || "TG"}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-xs font-medium">
                      {g.title}
                    </span>
                    <span className="mt-1 block text-[10px] text-indigo-100/40">
                      {g.members != null
                        ? `${g.members.toLocaleString()} members`
                        : g.id}
                      {!g.available ? " · access unconfirmed" : ""}
                    </span>
                  </span>
                </button>
              ))
            ) : (
              <div className="p-4 text-center">
                <Users className="mx-auto text-indigo-300/25" size={24} />
                <p className="mt-3 text-xs text-indigo-100/45">
                  {query ? "No matching groups" : "No groups loaded yet"}
                </p>
              </div>
            )}
          </div>
          <button
            disabled={loading || busy}
            onClick={() => void load()}
            className="mx-4 mb-3 text-[11px] text-indigo-200 underline disabled:opacity-40"
          >
            {loading ? "Refreshing groups…" : "Refresh conversations"}
          </button>
          {groupsError && (
            <p
              role="status"
              className="mx-3 mb-3 rounded-lg bg-amber-400/5 p-3 text-[11px] leading-5 text-amber-200/70"
            >
              {groupsError}
            </p>
          )}
          <div className="border-t border-indigo-300/10 p-4">
            <label htmlFor="chat-id" className="text-[11px] text-indigo-100/50">
              Or enter a chat ID / @username
            </label>
            <input
              id="chat-id"
              disabled={busy}
              value={chatId}
              onChange={(e) => select(e.target.value.trim())}
              placeholder="-100… or @channel"
              className="ios-input mt-2 text-xs"
              autoComplete="off"
            />
          </div>
        </aside>
        <div className="ios-card flex min-w-0 flex-col overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-indigo-300/10 p-4">
            <div className="flex min-w-0 items-center gap-3">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-indigo-400/10 text-indigo-300">
                <MessageCircle size={19} />
              </span>
              <div className="min-w-0">
                <h2 className="max-w-[260px] truncate text-sm font-semibold">
                  {title}
                </h2>
                <p className="mt-1 text-[10px] text-indigo-100/40">
                  {chatId
                    ? "Telegram delivery · plain text"
                    : "Select a group or enter a destination"}
                </p>
              </div>
            </div>
            <div
              className="flex rounded-xl border border-indigo-300/10 bg-black/15 p-1"
              aria-label="Send identity"
            >
              {[
                { user: false, label: "Bot Chat", icon: MessageCircle },
                { user: true, label: "Chat as User", icon: UserRound },
              ].map((mode) => (
                <button
                  key={mode.label}
                  aria-pressed={asUser === mode.user}
                  title={
                    mode.user && !userAvailable
                      ? "User session is not configured"
                      : mode.label
                  }
                  disabled={busy || (mode.user && !userAvailable)}
                  onClick={() => setAsUser(mode.user)}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-[10px] transition disabled:opacity-35 ${asUser === mode.user ? "bg-indigo-500/25 text-indigo-100" : "text-indigo-100/40"}`}
                >
                  <mode.icon size={13} />
                  {mode.label}
                </button>
              ))}
            </div>
          </div>
          <div
            className="chat-canvas flex h-[360px] flex-col gap-4 overflow-y-auto p-4 sm:h-[430px] sm:p-6"
            role="log"
            aria-label="Outgoing delivery receipts"
            aria-live="polite"
          >
            {!visible.length ? (
              <div className="m-auto max-w-xs text-center">
                <span className="mx-auto grid h-16 w-16 place-items-center rounded-3xl border border-indigo-400/15 bg-indigo-500/10 text-indigo-300">
                  <Send size={27} />
                </span>
                <h3 className="mt-5 text-base font-semibold">
                  Start a conversation
                </h3>
                <p className="mt-2 text-xs leading-6 text-indigo-100/40">
                  Your outgoing messages appear here when you send them.
                  Incoming Telegram messages aren’t synced to this workspace.
                </p>
              </div>
            ) : (
              visible.map((d) => (
                <div
                  key={d.key}
                  className="max-w-[90%] self-end sm:max-w-[80%]"
                >
                  <div
                    className={`rounded-2xl rounded-br-md border px-4 py-3 ${d.status === "failed" ? "border-red-400/25 bg-red-400/5" : "border-indigo-300/15 bg-gradient-to-br from-indigo-600 to-violet-700 shadow-lg shadow-indigo-950/30"}`}
                  >
                    <p className="whitespace-pre-wrap break-words text-sm leading-6">
                      {d.text}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center justify-end gap-1.5 text-[9px] text-indigo-100/65">
                      {d.time} · {d.via === "user" ? "User" : "Bot"}
                      {d.status === "sending" ? (
                        <>
                          <LoaderCircle size={11} className="animate-spin" />{" "}
                          Sending
                        </>
                      ) : d.status === "sent" ? (
                        <>
                          <CheckCheck size={12} /> Telegram accepted · #{d.id}
                        </>
                      ) : (
                        <>
                          <AlertCircle size={11} /> Delivery not confirmed
                        </>
                      )}
                    </div>
                  </div>
                  {d.status === "failed" && (
                    <p className="mt-2 max-w-sm text-[10px] leading-5 text-red-200/70">
                      {d.error} · Check Telegram before retrying; a network
                      failure can happen after delivery.
                    </p>
                  )}
                </div>
              ))
            )}
            <div ref={end} />
          </div>
          <div className="border-t border-indigo-300/10 p-3 sm:p-4">
            {error && (
              <div
                role="alert"
                className="mb-3 flex items-start gap-2 rounded-xl border border-red-300/15 bg-red-500/5 p-3 text-xs text-red-100"
              >
                <AlertCircle size={15} className="shrink-0" />
                {error}
              </div>
            )}
            <div className="mb-3 flex flex-wrap gap-2">
              {[
                "Thanks for being part of our community!",
                "Quick update: ",
                "Welcome! Please check the pinned messages.",
                "The next session starts at ",
              ].map((reply, i) => (
                <button
                  key={reply}
                  disabled={busy}
                  onClick={() => {
                    if (
                      text.trim() &&
                      !window.confirm(
                        "Replace the current message with this editable quick reply?",
                      )
                    )
                      return;
                    setText(reply);
                    composer.current?.focus();
                  }}
                  className="rounded-full border border-indigo-300/15 px-3 py-1.5 text-[10px] text-indigo-100/50"
                >
                  {
                    [
                      "Thank you",
                      "Quick update",
                      "Welcome",
                      "Session reminder",
                    ][i]
                  }
                </button>
              ))}
            </div>
            <label className="sr-only" htmlFor="message">
              Message text
            </label>
            <textarea
              id="message"
              ref={composer}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  (e.ctrlKey || e.metaKey) &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  void send();
                }
              }}
              placeholder={
                chatId
                  ? "Write something for your community…"
                  : "Choose a destination to get started…"
              }
              rows={3}
              maxLength={4096}
              className="ios-input resize-y text-sm"
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <span className="text-[10px] text-indigo-100/35">
                {text.length.toLocaleString()}/4,096 · Ctrl/⌘ + Enter to send
              </span>
              <button
                onClick={() => void send()}
                disabled={
                  busy ||
                  !chatId.trim() ||
                  !text.trim() ||
                  (asUser && !userAvailable)
                }
                className="ios-btn ios-btn-primary text-xs disabled:opacity-40"
              >
                {busy ? (
                  <LoaderCircle size={15} className="animate-spin" />
                ) : (
                  <Send size={15} />
                )}{" "}
                {busy ? "Sending…" : "Send message"}
              </button>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-indigo-300/5 px-4 py-3">
            <p className="text-[9px] text-indigo-100/30">
              Up to 100 outgoing receipts in memory · cleared on reload · not a
              Telegram inbox
            </p>
            <button
              disabled={busy || !deliveries.length}
              onClick={() => setDeliveries([])}
              className="flex items-center gap-1 text-[10px] text-indigo-200/40 hover:text-indigo-100 disabled:opacity-25"
            >
              <Trash2 size={11} /> Clear receipts
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
