"use client";

import { useEffect, useRef } from "react";
import { useStudio } from "./StudioProvider";

const hues: Record<string, number> = {
  home: 247, post: 192, tools: 218, guide: 264, arcade: 34, music: 153,
  chat: 199, groups: 226, federations: 282, automation: 165, analytics: 208,
  broadcast: 326, settings: 238, auth: 270,
};

const themeBases: Record<string, number> = { aurora: 247, glacier: 190, orchid: 286, ember: 25 };
function sectionHue(tab: string, theme = "aurora") {
  return ((themeBases[theme] ?? 247) + ((hues[tab] ?? 247) - 247) + 360) % 360;
}

type HueObject = { initialValue: { hue?: number } };

/** Motion is additive: every interaction remains usable when effects are unavailable or reduced. */
export function StudioMotion() {
  const { tab } = useStudio();
  const theatreHue = useRef<HueObject | null>(null);
  const activeTab = useRef(tab);

  useEffect(() => {
    let active = true;
    let unsubscribe = () => {};
    void import("@theatre/core").then(({ getProject, types }) => {
      if (!active) return;
      const project = getProject("Videl Studio Atmosphere");
      const sheet = project.sheet("Workspace");
      const theme = document.documentElement.dataset.studioTheme ?? "aurora";
      const accent = sheet.object("Active section", { hue: types.number(sectionHue(tab, theme)) });
      theatreHue.current = accent;
      unsubscribe = accent.onValuesChange(({ hue }) => {
        document.documentElement.style.setProperty("--studio-hue", `${hue}deg`);
      });
      accent.initialValue = { hue: sectionHue(tab, theme) };
    }).catch(() => {});
    return () => {
      active = false;
      unsubscribe();
      theatreHue.current = null;
    };
  }, []);

  useEffect(() => {
    activeTab.current = tab;
    const accent = theatreHue.current;
    if (accent) accent.initialValue = { hue: sectionHue(tab, document.documentElement.dataset.studioTheme ?? "aurora") };

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let active = true;
    const panel = document.querySelector<HTMLElement>(`#studio-panel [data-panel="${tab}"]`);
    void import("gsap").then(({ gsap }) => {
      if (!active || !panel) return;
      document.querySelector("#studio-panel")?.setAttribute("data-gsap-active", "true");
      gsap.killTweensOf(panel);
      gsap.fromTo(panel,
        { autoAlpha: 0, y: 12, filter: "blur(8px)" },
        { autoAlpha: 1, y: 0, filter: "blur(0px)", duration: 0.42, ease: "power2.out", clearProps: "filter,transform,opacity,visibility" },
      );
    }).catch(() => {});
    void import("velocity-animate").then(({ default: Velocity }) => {
      const topbar = document.querySelector<HTMLElement>(".studio-topbar");
      if (active && topbar) Velocity.animate(topbar, { opacity: [1, 0.72], translateY: [0, -3] }, { duration: 230, easing: "easeOutCubic" });
    }).catch(() => {});
    return () => { active = false; };
  }, [tab]);

  useEffect(() => {
    const updateTheme = () => {
      const accent = theatreHue.current;
      if (accent) accent.initialValue = { hue: sectionHue(activeTab.current, document.documentElement.dataset.studioTheme ?? "aurora") };
    };
    window.addEventListener("videl:studio-theme", updateTheme);
    return () => window.removeEventListener("videl:studio-theme", updateTheme);
  }, []);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (reduced.matches) return;
    let active = true;
    let instance: { stop: () => unknown; reset: () => unknown } | undefined;
    void import("vivus").then(({ default: Vivus }) => {
      const mark = document.getElementById("videl-studio-mark");
      if (active && mark) instance = new Vivus(mark.id, { duration: 72, type: "oneByOne", start: "autostart" });
    }).catch(() => {});
    return () => { active = false; instance?.stop(); instance?.reset(); };
  }, []);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>("[data-motion-burst], .ios-btn-primary") : null;
      if (!target || target.matches(":disabled,[aria-disabled='true']")) return;
      void import("@mojs/core").then(({ default: mojs }) => {
        const burst = new mojs.Burst({
          parent: target,
          radius: { 0: 42 },
          count: 7,
          children: { shape: "circle", fill: ["#a5b4fc", "#67e8f9", "#f0abfc"], radius: { 3: 0 }, duration: 480, easing: "cubic.out" },
        });
        burst.replay();
        window.setTimeout(() => burst.el?.remove(), 700);
      }).catch(() => {});
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);

  return null;
}
