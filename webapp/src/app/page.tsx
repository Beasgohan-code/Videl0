"use client";
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useTelegram } from "@/components/TelegramProvider";
import { canOpenSection } from "@/lib/access";
import { useStudio } from "@/components/studio/StudioProvider";
import { PanelBoundary } from "@/components/studio/PanelBoundary";
import { OwnerGate } from "@/components/studio/OwnerGate";
import { BackendStatus } from "@/components/studio/BackendStatus";
import { ToolFinder } from "@/components/studio/ToolFinder";
import Home from "@/components/studio/screens/Home";
const loading = () => (
  <div className="py-20 text-center text-indigo-200/50" role="status">
    Opening your workspace…
  </div>
);
const screens = {
  home: Home,
  tools: dynamic(() => import("@/components/studio/screens/Tools"), { loading }),
  guide: dynamic(() => import("@/components/studio/screens/Guide"), { loading }),
  chat: dynamic(() => import("@/components/studio/screens/Chat"), { loading }),
  post: dynamic(() => import("@/components/studio/screens/Post"), { loading }),
  groups: dynamic(() => import("@/components/studio/screens/Groups"), {
    loading,
  }),
  automation: dynamic(() => import("@/components/studio/screens/Automation"), {
    loading,
  }),
  analytics: dynamic(() => import("@/components/studio/screens/Analytics"), {
    loading,
  }),
  broadcast: dynamic(() => import("@/components/studio/screens/Broadcast"), {
    loading,
  }),
  settings: dynamic(() => import("@/components/studio/screens/Settings"), {
    loading,
  }),
  auth: dynamic(() => import("@/components/studio/screens/Auth"), { loading }),
};
export default function Studio() {
  const { tab } = useStudio();
  const { authenticated } = useTelegram();
  const [visited, setVisited] = useState<string[]>(["home"]);
  useEffect(() => {
    setVisited((current) =>
      current.includes(tab) ? current : [...current, tab],
    );
  }, [tab]);
  return (
    <div className="studio-panel">
      {authenticated && <BackendStatus />}
      {tab !== 'chat' && <ToolFinder />}
      <div className="sr-only" aria-live="polite">
        {tab} panel
      </div>
      {Object.entries(screens).map(([key, Screen]) =>
        canOpenSection(key, authenticated) && (visited.includes(key) || key === tab) ? (
          <div key={key} hidden={key !== tab}>
            <PanelBoundary name={key}>
              {[
                "chat",
                "groups",
                "automation",
                "analytics",
                "broadcast",
                "settings",
              ].includes(key) ? (
                <OwnerGate>
                  <Screen />
                </OwnerGate>
              ) : (
                <Screen />
              )}
            </PanelBoundary>
          </div>
        ) : null,
      )}
    </div>
  );
}
