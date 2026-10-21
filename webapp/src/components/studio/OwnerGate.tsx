"use client";
import { Loader2, ShieldCheck } from "lucide-react";
import { useTelegram } from "@/components/TelegramProvider";
import { useStudio } from "./StudioProvider";
import { Callout, LoadingState } from "./ui";
export function OwnerGate({ children }: { children: React.ReactNode }) {
  const { authenticated, authError, retryAuth } = useTelegram();
  const { open } = useStudio();
  if (authenticated) return children;
  return (
    <main className="ios-page ios-page-narrow">
      <div className="ios-card p-6 sm:p-9">
        {authenticated === null ? (
          <>
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-indigo-400/10 text-indigo-300">
              <Loader2 size={22} className="animate-spin" aria-hidden />
            </span>
            <p className="ios-caps ios-eyebrow mt-5">Private workspace</p>
            <h1 className="ios-title mt-2">Checking your owner session…</h1>
            <LoadingState className="mt-5" label="Checking your owner session" rows={3} />
          </>
        ) : (
          <>
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-indigo-400/10 text-indigo-300">
              <ShieldCheck size={24} aria-hidden />
            </span>
            <p className="ios-caps ios-eyebrow mt-5">Private workspace</p>
            <h1 className="ios-title mt-2">Sign in to open this tool</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--ios-label-secondary)]">
              Chat, group settings, broadcasts and private analytics require your
              verified Telegram owner account. Post Studio and creator tools are
              available without signing in.
            </p>
            {authError && (
              <Callout tone="danger" className="mt-4">
                {authError}
              </Callout>
            )}
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                onClick={() => open("auth")}
                className="ios-btn ios-btn-primary text-sm"
              >
                Open owner sign-in
              </button>
              <button
                onClick={() => void retryAuth()}
                className="ios-btn ios-btn-glass text-sm"
              >
                Check session again
              </button>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
