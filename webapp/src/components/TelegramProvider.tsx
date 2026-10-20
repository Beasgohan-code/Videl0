"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { telegramLaunchData } from "@/lib/telegram-launch";

type TelegramUser = {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
};
type TelegramContextValue = {
  available: boolean;
  user: TelegramUser | null;
  authenticated: boolean | null;
  authError: string;
  retryAuth: () => Promise<void>;
  logout: () => Promise<void>;
};
const TelegramContext = createContext<TelegramContextValue>({
  available: false,
  user: null,
  authenticated: null,
  authError: "",
  retryAuth: async () => {},
  logout: async () => {},
});
declare global {
  interface Window {
    Telegram?: any;
  }
}

export function TelegramProvider({ children }: { children: React.ReactNode }) {
  const [value, setValue] = useState({
    available: false,
    user: null as TelegramUser | null,
    authenticated: null as boolean | null,
    authError: "",
  });
  const alive = useRef(false);
  const inFlight = useRef(false);
  const rerun = useRef(false);
  const retryAuth = useCallback(async (): Promise<void> => {
    if (inFlight.current) {
      rerun.current = true;
      return;
    }
    inFlight.current = true;
    const tg = window.Telegram?.WebApp;
    let initData = telegramLaunchData(
      tg?.initData,
      window.location.search,
      window.location.hash,
    );
    let available = Boolean(initData); // SDK presence alone does not mean this is a Mini App.
    if (alive.current)
      setValue((v) => ({
        ...v,
        available,
        authenticated: null,
        authError: "",
      }));
    try {
      // Always restore the HttpOnly session first, including in a normal browser.
      const session = await fetch("/api/auth", {
        credentials: "same-origin",
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      });
      const existing = await session.json();
      if (!initData && session.ok && existing.owner === true) {
        if (alive.current)
          setValue((v) => ({
            ...v,
            available,
            authenticated: true,
            authError: "",
          }));
        return;
      }
      initData = telegramLaunchData(
        window.Telegram?.WebApp?.initData,
        window.location.search,
        window.location.hash,
      );
      available = Boolean(initData);
      if (!initData) {
        if (alive.current)
          setValue((v) => ({
            ...v,
            available: false,
            authenticated: false,
            authError: "",
          }));
        return;
      }
      const response = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initData }),
        credentials: "same-origin",
        cache: "no-store",
        signal: AbortSignal.timeout(15000),
      });
      const result = await response.json();
      if (!response.ok || result.owner !== true)
        throw new Error(result.error || "Telegram owner verification failed");
      // Detect blocked cookies now instead of saying verified while all controls fail.
      const check = await fetch("/api/auth", {
        credentials: "same-origin",
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      });
      const confirmed = await check.json();
      if (!check.ok || confirmed.owner !== true)
        throw new Error(
          "Telegram verified you, but this browser blocked the owner session. Open Studio in your browser and sign in there, or allow site cookies.",
        );
      if (alive.current)
        setValue({
          available,
          user: result.user ?? null,
          authenticated: true,
          authError: "",
        });
    } catch (error) {
      if (alive.current)
        setValue((v) => ({
          ...v,
          available,
          authenticated: false,
          authError:
            error instanceof Error
              ? error.message
              : "Owner connection failed. Please retry.",
        }));
    } finally {
      inFlight.current = false;
      if (rerun.current && alive.current) {
        rerun.current = false;
        queueMicrotask(() => void retryAuth());
      }
    }
  }, []);
  const logout = useCallback(async () => {
    try {
      const response = await fetch("/api/auth", {
        method: "DELETE",
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error("Sign out failed. Please retry.");
      setValue({
        available: false,
        user: null,
        authenticated: false,
        authError: "",
      });
      window.location.assign("/");
    } catch (error) {
      setValue((v) => ({
        ...v,
        authError: error instanceof Error ? error.message : "Sign out failed",
      }));
    }
  }, []);
  useEffect(() => {
    alive.current = true;
    let script: HTMLScriptElement | null = null;
    const setup = () => {
      const tg = window.Telegram?.WebApp;
      try {
        tg?.ready();
        tg?.expand();
        tg?.setHeaderColor?.("#080b1a");
        tg?.setBackgroundColor?.("#080b1a");
      } catch {}
      void retryAuth();
    };
    // Session restoration works even if telegram.org is blocked or loads slowly.
    setup();
    if (!window.Telegram?.WebApp) {
      script = document.createElement("script");
      script.src = "https://telegram.org/js/telegram-web-app.js";
      script.async = true;
      script.onload = setup;
      document.head.appendChild(script);
    }
    const onViewport = () =>
      document.documentElement.style.setProperty(
        "--tg-viewport-height",
        `${window.Telegram?.WebApp?.viewportHeight || window.innerHeight}px`,
      );
    window.addEventListener("resize", onViewport);
    onViewport();
    return () => {
      alive.current = false;
      window.removeEventListener("resize", onViewport);
      script?.remove();
    };
  }, [retryAuth]);
  return (
    <TelegramContext.Provider value={{ ...value, retryAuth, logout }}>
      {children}
    </TelegramContext.Provider>
  );
}
export function useTelegram() {
  return useContext(TelegramContext);
}
