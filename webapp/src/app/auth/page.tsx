"use client";
import { useState } from "react";
import { TelegramLogin } from "@/components/auth/TelegramLogin";
import Link from "next/link";

export default function AuthPage() {
  const [status, setStatus] = useState<string | null>(null);
  const botUsername = process.env.NEXT_PUBLIC_BOT_USERNAME || "Videl0Bot";
  const ownerId = process.env.NEXT_PUBLIC_OWNER_ID || "";

  return (
    <main className="mx-auto max-w-[520px] px-4 py-10">
      <div className="ios-card-elevated p-8 text-center animate-spring">
        <div className="h-16 w-16 mx-auto rounded-[16px] bg-white text-black flex items-center justify-center text-xl font-black">◍</div>
        <h1 className="ios-title mt-5">Sign in with Telegram</h1>
        <p className="ios-subheadline mt-2">Only the <b>owner</b> can open Studio & Chat. We verify via Telegram Login Widget + OWNER_ID.</p>

        <div className="mt-8 p-4 rounded-[16px] bg-[var(--ios-fill-secondary)] border border-[var(--ios-border)]">
          <div className="flex justify-center">
            <TelegramLogin
              botUsername={botUsername}
              onAuth={async (u) => {
                setStatus("Verifying…");
                try {
                  const r = await fetch("/api/auth", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(u) });
                  const j = await r.json();
                  if (j.ok) {
                    localStorage.setItem("videl_tg_user", JSON.stringify(u));
                    setStatus("✅ Verified — redirecting…");
                    setTimeout(() => location.href = "/dashboard", 800);
                  } else {
                    setStatus(`❌ ${j.error}`);
                  }
                } catch (e: any) { setStatus(`❌ ${String(e)}`); }
              }}
            />
          </div>
          {status && <p className="mt-4 ios-caption text-center">{status}</p>}
        </div>

        <div className="mt-6 grid grid-cols-2 gap-3 text-left ios-caption">
          <div className="ios-card p-3"><b>Bot</b><br/>@{botUsername}<br/><span className="text-[var(--ios-label-tertiary)]">Set at @BotFather /setdomain → your Vercel domain</span></div>
          <div className="ios-card p-3"><b>Owner</b><br/><code>{ownerId || "—"}</code><br/><span className="text-[var(--ios-label-tertiary)]">From env OWNER_ID</span></div>
        </div>

        <div className="mt-6 flex gap-2 justify-center">
          <Link href="/" className="ios-btn ios-btn-glass">Home</Link>
          <Link href="/dashboard" className="ios-btn ios-btn-primary">Dashboard</Link>
        </div>

        <p className="ios-caption mt-6 leading-relaxed">
          Troubleshooting: if hash invalid, re-add domain in @BotFather with <code>vercel.app</code> / your custom domain and redeploy with <code>BOT_TOKEN</code> + <code>OWNER_ID</code> env.
        </p>
      </div>
    </main>
  );
}
