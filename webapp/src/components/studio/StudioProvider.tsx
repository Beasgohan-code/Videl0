"use client";
import { useTelegram } from "@/components/TelegramProvider";
import { canOpenSection } from "@/lib/access";
import { createContext, useContext, useEffect, useState } from "react";
export const sections = [
  "home",
  "chat",
  "post",
  "tools",
  "guide",
  "groups",
  "federations",
  "automation",
  "analytics",
  "broadcast",
  "settings",
  "auth",
  "arcade",
] as const;
export type Section = (typeof sections)[number];
const legacy: Record<string, Section> = {
  "/": "home",
  "/dashboard": "home",
  "/dashboard/chat": "chat",
  "/chat": "chat",
  "/dashboard/channel": "post",
  "/post": "post",
  "/help": "guide",
  "/guide": "guide",
  "/groups": "groups",
  "/federations": "federations",
  "/automation": "automation",
  "/analytics": "analytics",
  "/broadcast": "broadcast",
  "/settings": "settings",
  "/auth": "auth",
  "/arcade": "arcade",
  "/play": "arcade",
};
const StudioContext = createContext<{
  tab: Section;
  open: (tab: Section) => void;
  selectedGroup: number | null;
  selectGroup: (id: number) => void;
}>({ tab: "home", open: () => {}, selectedGroup: null, selectGroup: () => {} });
export function StudioProvider({ children }: { children: React.ReactNode }) {
  const [tab, setTab] = useState<Section>("home");
  const { authenticated } = useTelegram();
  const [selectedGroup, selectGroup] = useState<number|null>(null);
  const safeTab = canOpenSection(tab, authenticated) ? tab : "home";
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initial = params.get("tab");
    if (sections.includes(initial as Section)) setTab(initial as Section);
    // A shared command link keeps working after the tab parameter is stripped.
    else if (params.get("cmd")) setTab("guide");
    // Deep links choose a panel, but the workspace itself always stays at the root URL.
    if (initial) {
      const url = new URL(window.location.href);
      url.searchParams.delete("tab");
      window.history.replaceState(
        window.history.state,
        "",
        url.pathname + url.search + url.hash,
      );
    }
  }, []);
  function capture(e: React.MouseEvent<HTMLDivElement>) {
    if (
      e.defaultPrevented ||
      e.button !== 0 ||
      e.metaKey ||
      e.ctrlKey ||
      e.shiftKey ||
      e.altKey
    )
      return;
    const a = (e.target as Element).closest("a");
    if (!a || a.target === "_blank" || a.hasAttribute("download")) return;
    const url = new URL(a.href, window.location.href);
    if (url.origin !== window.location.origin) return;
    const target = url.searchParams.get("tab") as Section | null;
    const next =
      target && sections.includes(target) ? target : legacy[url.pathname];
    if (next) {
      e.preventDefault();
      e.stopPropagation();
      setTab(next);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }
  return (
    <StudioContext.Provider value={{ tab: safeTab, open: setTab, selectedGroup, selectGroup }}>
      <div onClickCapture={capture}>{children}</div>
    </StudioContext.Provider>
  );
}
export function useStudio() {
  return useContext(StudioContext);
}
