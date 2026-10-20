"use client";
import { ShieldCheck } from "lucide-react";
import { useTelegram } from "@/components/TelegramProvider";
import { useStudio } from "./StudioProvider";
export function OwnerGate({ children }: { children: React.ReactNode }) {
  const { authenticated, authError, retryAuth } = useTelegram();
  const { open } = useStudio();
  if (authenticated) return children;
  return (
    <section className="mx-auto my-10 max-w-xl rounded-3xl border border-indigo-300/15 bg-indigo-400/5 p-6 sm:p-9">
      <ShieldCheck className="text-indigo-300" size={30} />
      <p className="ios-caps mt-5 text-[11px] text-indigo-200/50">
        PRIVATE WORKSPACE
      </p>
      <h1 className="mt-2 text-2xl font-semibold">
        {authenticated === null
          ? "Checking your owner session…"
          : "Sign in to open this tool"}
      </h1>
      <p className="mt-3 text-sm leading-6 text-indigo-100/55">
        Chat, group settings, broadcasts and private analytics require your
        verified Telegram owner account. Post Studio and creator tools
        are available without signing in.
      </p>
      {authError && (
        <p role="alert" className="mt-4 text-sm text-amber-200">
          {authError}
        </p>
      )}
      <div className="mt-6 flex flex-wrap gap-3">
        <button
          onClick={() => open("auth")}
          className="ios-btn ios-btn-primary text-sm"
        >
          Open owner sign-in
        </button>
        <button
          disabled={authenticated === null}
          onClick={() => void retryAuth()}
          className="ios-btn ios-btn-glass text-sm disabled:opacity-40"
        >
          Check session again
        </button>
      </div>
    </section>
  );
}
