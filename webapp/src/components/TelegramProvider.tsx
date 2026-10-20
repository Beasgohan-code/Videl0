"use client";
import { useEffect, useState } from "react";

declare global {
  interface Window {
    Telegram?: any;
  }
}

export function TelegramProvider({ children }: { children: React.ReactNode }) {
  const [isTelegram, setIsTelegram] = useState(false);

  useEffect(() => {
    // Load Telegram WebApp script if not loaded
    if (typeof window !== "undefined" && !window.Telegram) {
      const script = document.createElement("script");
      script.src = "https://telegram.org/js/telegram-web-app.js";
      script.async = true;
      script.onload = () => {
        try {
          const tg = window.Telegram?.WebApp;
          if (tg) {
            tg.ready();
            tg.expand();
            // Enable closing confirmation if needed
            // tg.enableClosingConfirmation();
            
            // Set header color to match app
            try {
              tg.setHeaderColor("#000000");
              tg.setBackgroundColor("#000000");
            } catch {}
            
            setIsTelegram(true);
            
            // Haptic on load (subtle)
            try { tg.HapticFeedback?.impactOccurred("light"); } catch {}
            
            // Handle theme changes
            const updateTheme = () => {
              try {
                document.documentElement.style.setProperty(
                  "--tg-theme-bg",
                  tg.themeParams?.bg_color || "#000000"
                );
              } catch {}
            };
            updateTheme();
            tg.onEvent?.("themeChanged", updateTheme);
          }
        } catch {}
      };
      document.head.appendChild(script);
    } else if (window.Telegram?.WebApp) {
      try {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        setIsTelegram(true);
      } catch {}
    }

    // Handle viewport
    const handleViewport = () => {
      const vh = window.innerHeight * 0.01;
      document.documentElement.style.setProperty("--vh", `${vh}px`);
      document.documentElement.style.setProperty(
        "--tg-viewport-height", 
        `${window.Telegram?.WebApp?.viewportHeight || window.innerHeight}px`
      );
    };
    handleViewport();
    window.addEventListener("resize", handleViewport);
    return () => window.removeEventListener("resize", handleViewport);
  }, []);

  return <>{children}</>;
}

export function useTelegram() {
  if (typeof window === "undefined") return null;
  return window.Telegram?.WebApp || null;
}
