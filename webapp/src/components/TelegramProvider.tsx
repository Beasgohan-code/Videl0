"use client";
import { createContext, useContext, useEffect, useState } from "react";

type TelegramUser = { id: number; first_name: string; last_name?: string; username?: string };
type TelegramContextValue = { available: boolean; user: TelegramUser | null; authenticated: boolean | null };
const TelegramContext = createContext<TelegramContextValue>({ available: false, user: null, authenticated: null });

declare global { interface Window { Telegram?: any } }

export function TelegramProvider({ children }: { children: React.ReactNode }) {
  const [value, setValue] = useState<TelegramContextValue>({ available: false, user: null, authenticated: null });

  useEffect(() => {
    let cancelled = false;
    let script: HTMLScriptElement | null = null;
    const initialize = async () => {
      const tg = window.Telegram?.WebApp;
      if (!tg) return;
      try { tg.ready(); tg.expand(); tg.setHeaderColor?.("#080b1a"); tg.setBackgroundColor?.("#080b1a"); } catch { /* older Telegram clients */ }
      const user = tg.initDataUnsafe?.user ?? null;
      document.documentElement.style.setProperty("--tg-viewport-height", `${tg.viewportHeight || window.innerHeight}px`);
      document.documentElement.classList.add("tg-miniapp");
      if (cancelled) return;
      setValue({ available: true, user, authenticated: null });
      if (!tg.initData || !user) { setValue({ available: true, user, authenticated: false }); return; }
      try {
        const response = await fetch("/api/auth", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ initData: tg.initData }), credentials: "same-origin", cache: "no-store" });
        const result = await response.json();
        if (!cancelled) setValue({ available: true, user, authenticated: response.ok && result.owner === true });
      } catch {
        if (!cancelled) setValue({ available: true, user, authenticated: false });
      }
    };
    if (window.Telegram?.WebApp) void initialize();
    else {
      script = document.createElement("script"); script.src = "https://telegram.org/js/telegram-web-app.js"; script.async = true;
      script.onload = () => { void initialize(); }; document.head.appendChild(script);
    }
    const onViewport = () => document.documentElement.style.setProperty("--tg-viewport-height", `${window.Telegram?.WebApp?.viewportHeight || window.innerHeight}px`);
    window.addEventListener("resize", onViewport);
    window.Telegram?.WebApp?.onEvent?.("viewportChanged", onViewport);
    window.Telegram?.WebApp?.onEvent?.("themeChanged", () => {
      const color = window.Telegram?.WebApp?.themeParams?.bg_color || "#080b1a";
      document.documentElement.style.setProperty("--tg-theme-bg", color);
    });
    return () => { cancelled = true; window.removeEventListener("resize", onViewport); if (script?.parentNode) script.parentNode.removeChild(script); };
  }, []);

  return <TelegramContext.Provider value={value}>{children}</TelegramContext.Provider>;
}

export function useTelegram() { return useContext(TelegramContext); }
