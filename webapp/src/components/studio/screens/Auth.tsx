"use client";
import { useState } from "react";
import Link from "next/link";
import { TelegramLogin } from "@/components/auth/TelegramLogin";
import { useTelegram } from "@/components/TelegramProvider";
import { ArrowLeft, CircleAlert, ShieldCheck } from "lucide-react";
export default function AuthPage() {
  const telegram = useTelegram();
  const [status, setStatus] = useState("");
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const botUsername = (
    process.env.NEXT_PUBLIC_BOT_USERNAME || "Videl0Bot"
  ).replace(/^@/, "");
  async function authenticate(user: unknown) {
    if (busy) return;
    setBusy(true);
    setStatus("Verifying Telegram identity…");
    setFailed(false);
    try {
      const response = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login_widget: user }),
        credentials: "same-origin",
        cache: "no-store",
        signal: AbortSignal.timeout(15000),
      });
      const data = await response.json();
      if (!response.ok || !data.ok)
        throw new Error(data.error || "Owner verification failed");
      const check = await fetch("/api/auth", {
        credentials: "same-origin",
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      });
      const session = await check.json();
      if (!check.ok || !session.owner)
        throw new Error(
          "Telegram verified you, but the session cookie was blocked. Allow site cookies or sign in from your regular browser.",
        );
      try {
        sessionStorage.removeItem("videl_signed_out");
      } catch {}
      setStatus("Owner session confirmed. Opening Studio…");
      window.location.assign("/");
    } catch (error) {
      setFailed(true);
      setStatus(
        error instanceof Error
          ? error.message
          : "Owner verification failed. Please retry.",
      );
    } finally {
      setBusy(false);
    }
  }
  const message = status || telegram.authError;
  return (
    <main className="mx-auto max-w-lg py-8 sm:py-14">
      <section className="ios-card p-6 text-center sm:p-9">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-blue-400 to-indigo-600 text-white">
          <ShieldCheck size={25} />
        </span>
        <p className="mt-5 ios-caption2">SECURE OWNER ACCESS</p>
        <h1 className="mt-2 ios-title">
          {telegram.authenticated
            ? "Owner access verified"
            : "Sign in with Telegram"}
        </h1>
        {telegram.authenticated ? (
          <>
            <p className="mt-3 text-sm text-emerald-200">
              Your owner session is active. Private controls are available.
            </p>
            <Link href="/" className="ios-btn ios-btn-primary mt-6">
              Open Studio
            </Link>
          </>
        ) : (
          <>
            <p className="mt-3 text-sm leading-6 text-[var(--ios-label-secondary)]">
              Only Telegram account 6265999542 can open private controls.
              Everyone can use Post Studio and Creator Tools without signing in.
              No tokens or passwords are needed here.
            </p>
            {telegram.available ? (
              <div className="mt-6 rounded-xl border border-indigo-300/20 p-4">
                <p className="text-sm">Telegram Mini App detected</p>
                <p className="mt-2 text-xs text-white/50">
                  We verify the signed launch data automatically. If it expired,
                  close this Mini App and launch it again from the bot.
                </p>
                <button
                  disabled={telegram.authenticated === null || busy}
                  onClick={() => {
                    setStatus("");
                    void telegram.retryAuth();
                  }}
                  className="ios-btn ios-btn-primary mt-4 text-sm disabled:opacity-40"
                >
                  {telegram.authenticated === null
                    ? "Checking owner access…"
                    : "Retry Telegram verification"}
                </button>
              </div>
            ) : (
              <div className="mt-7 rounded-2xl border border-white/[0.07] bg-black/20 p-4">
                <TelegramLogin
                  botUsername={botUsername}
                  onAuth={authenticate}
                />
              </div>
            )}
            <a
              href={`https://t.me/${botUsername}?start=studio`}
              target="_blank"
              rel="noreferrer"
              className="ios-btn ios-btn-glass mt-4 w-full text-sm"
            >
              Open bot to launch Studio
            </a>
            <p className="mt-2 text-xs leading-5 text-white/45">
              In the bot, tap its Studio / Web App button. A regular pasted
              website link does not include Telegram identity.
            </p>
          </>
        )}
        {message && (
          <p
            role={failed || telegram.authError ? "alert" : "status"}
            className="mt-4 flex items-start justify-center gap-2 rounded-xl border border-amber-300/20 p-3 text-left text-sm text-amber-100"
          >
            <CircleAlert size={16} className="mt-0.5 shrink-0" />
            {message}
          </p>
        )}
        {!telegram.authenticated && (
          <details className="mt-6 rounded-xl bg-white/[0.035] p-3 text-left text-xs leading-5 text-[var(--ios-label-secondary)]">
            <summary className="cursor-pointer font-semibold">
              If Telegram sign-in still fails
            </summary>
            <p className="mt-3">
              For browser login, the bot’s BotFather /setdomain must be{" "}
              <code>videl-studio.vercel.app</code>. On Render,{" "}
              <code>OWNER_ID</code> must be your numeric Telegram user ID, and{" "}
              <code>BOT_TOKEN</code> must belong to @{botUsername}. Do not share
              your token here.
            </p>
            <p className="mt-2">
              Mini App verification errors appear above. Vercel and Render must
              share the same server-side <code>WEBAPP_SECRET</code>.
            </p>
          </details>
        )}
        <div className="mt-6 flex justify-center">
          <Link href="/" className="ios-btn ios-btn-glass text-sm">
            <ArrowLeft size={15} /> Back to Videl
          </Link>
        </div>
      </section>
    </main>
  );
}
