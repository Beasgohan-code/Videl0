"use client";
import { useCallback, useEffect, useState } from "react";
type BotConfig = {
  bot?: { first_name?: string; username?: string };
  commands?: { command: string; description: string }[] | null;
  warnings?: string[];
  webapp_url?: string;
};
export function BotControls() {
  const [data, setData] = useState<BotConfig | null>(null);
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/bot-settings", {
        cache: "no-store",
        signal: AbortSignal.timeout(12000),
      });
      const next = await response.json();
      if (!response.ok || !next.ok)
        throw new Error(next.error || "Settings unavailable");
      setData(next);
      setUrl((current) => current || next.webapp_url || window.location.origin);
    } catch (error) {
      setData(null);
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not verify Telegram settings",
      );
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  async function update(action: string) {
    setBusy(true);
    setMessage("");
    try {
      const r = await fetch("/api/bot-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          webapp_url: url,
          button_text: "Videl 👑 Studio",
        }),
      });
      const d = await r.json();
      if (!r.ok || !d.ok) throw new Error(d.error || "Update failed");
      await load();
      setMessage(
        action === "sync_commands"
          ? `Telegram confirmed ${d.synced} commands synced.`
          : "Telegram confirmed the menu button update. Set WEBAPP_URL on the backend to the same root URL so restart and inline buttons stay consistent.",
      );
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="ios-card mt-5 p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold">Bot Settings · Commands & WebApp</h2>
        <button
          disabled={loading || busy}
          onClick={() => {
            setMessage("");
            void load();
          }}
          className="ios-btn ios-btn-glass text-xs"
        >
          {loading ? "Checking…" : "Reload from Telegram"}
        </button>
      </div>
      <p className="ios-caption mt-2">
        {data?.bot
          ? `${data.bot.first_name} · @${data.bot.username}`
          : loading
            ? "Verifying configuration with Telegram…"
            : "Telegram configuration not verified. Sign in as owner or retry the connection."}
      </p>
      <label className="mt-5 block text-sm">
        Single Web App URL
        <input
          className="ios-input mt-2"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://your-project.vercel.app"
          type="url"
        />
      </label>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          className="ios-btn ios-btn-primary disabled:opacity-40"
          disabled={busy || loading || !data || !url.startsWith("https://")}
          onClick={() => void update("set_menu_button")}
        >
          Update Telegram menu
        </button>
        <button
          className="ios-btn ios-btn-glass disabled:opacity-40"
          disabled={busy || loading || !data}
          onClick={() => void update("sync_commands")}
        >
          Sync bot commands
        </button>
      </div>
      {data?.warnings?.map((warning) => (
        <p key={warning} role="status" className="mt-3 text-xs text-amber-200">
          {warning} · Reload to check again.
        </p>
      ))}
      {message && (
        <p
          role="status"
          className="mt-4 rounded-xl border border-indigo-300/20 p-3 text-sm"
        >
          {message}
        </p>
      )}
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {data?.commands?.map((c) => (
          <div key={c.command} className="rounded-xl bg-white/5 p-3 text-xs">
            <code className="text-indigo-200">/{c.command}</code>
            <span className="ml-2 text-white/50">{c.description}</span>
          </div>
        ))}
      </div>
      <p className="ios-caption mt-4">
        Tokens and API secrets remain server-side. Inline mode is managed
        through BotFather, not simulated here.
      </p>
    </section>
  );
}
