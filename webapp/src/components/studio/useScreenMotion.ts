"use client";

import { useEffect, type RefObject } from "react";

/** GSAP handles the narrative entrance; anime.js staggers the card grid. */
export function useScreenMotion(rootRef: RefObject<HTMLElement | null>, key: string | number) {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let active = true;
    let context: { revert: () => void } | undefined;
    let anime: typeof import("animejs") | undefined;
    let staggerTargets: NodeListOf<HTMLElement> | undefined;

    void Promise.all([import("gsap"), import("animejs")]).then(([{ gsap }, animeModule]) => {
      if (!active || !rootRef.current) return;
      anime = animeModule.default as unknown as typeof import("animejs");
      const root = rootRef.current;
      const introTargets = root.querySelectorAll<HTMLElement>("[data-screen-intro]");
      staggerTargets = root.querySelectorAll<HTMLElement>("[data-screen-stagger]");

      context = gsap.context(() => {
        gsap.fromTo(introTargets,
          { autoAlpha: 0, y: 18, filter: "blur(7px)" },
          { autoAlpha: 1, y: 0, filter: "blur(0px)", duration: 0.62, stagger: 0.08, ease: "power3.out", clearProps: "all" },
        );
      }, root);

      anime({
        targets: staggerTargets,
        opacity: [0, 1],
        translateY: [16, 0],
        delay: anime.stagger(62, { start: 170 }),
        duration: 600,
        easing: "easeOutExpo",
      });
    }).catch(() => {});

    return () => {
      active = false;
      context?.revert();
      if (anime && staggerTargets) anime.remove(staggerTargets);
    };
  }, [rootRef, key]);
}
