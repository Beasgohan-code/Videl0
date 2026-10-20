"use client";
import { useEffect, useRef, useState } from "react";
type TelegramLoginUser = {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
};
declare global {
  interface Window {
    onTelegramAuth?: (user: TelegramLoginUser) => void;
  }
}
export function TelegramLogin({
  botUsername,
  onAuth,
  cornerRadius = 14,
}: {
  botUsername: string;
  onAuth: (user: TelegramLoginUser) => void | Promise<void>;
  cornerRadius?: number;
}) {
  const host = useRef<HTMLDivElement>(null);
  const callback = useRef(onAuth);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const [attempt, retry] = useState(0);
  callback.current = onAuth;
  useEffect(() => {
    setLoaded(false);
    setFailed(false);
    const username = botUsername.replace(/^@/, "");
    if (!username || !host.current) return;
    window.onTelegramAuth = (user) => {
      void callback.current(user);
    };
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", username);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", String(cornerRadius));
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.onload = () => setLoaded(true);
    script.onerror = () => {
      setLoaded(true);
      setFailed(true);
    };
    host.current.replaceChildren(script);
    return () => {
      script.remove();
      delete window.onTelegramAuth;
    };
  }, [botUsername, cornerRadius, attempt]);
  return (
    <div className="flex flex-col items-center gap-3">
      <div
        ref={host}
        className="flex min-h-[44px] items-center justify-center"
      />
      {!loaded && <p className="ios-caption">Loading Telegram sign-in…</p>}
      {failed && (
        <div role="alert" className="text-xs text-amber-200">
          Telegram sign-in could not load. Check your connection or launch
          Studio from the bot.
          <button
            onClick={() => retry((n) => n + 1)}
            className="ml-2 underline"
          >
            Retry
          </button>
        </div>
      )}
      <p className="max-w-[320px] text-center ios-caption">
        Telegram verifies the account. Videl grants access only to the
        configured bot owner.
      </p>
    </div>
  );
}
