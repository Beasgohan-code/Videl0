"use client";
import { useEffect, useState } from "react";
import { ArrowRight, Check, Circle, Clock3, Eye, PenLine, Sparkles } from "lucide-react";

/**
 * The Post Studio flow.
 *
 * A post is four decisions in a fixed order — what it says, what it looks like,
 * who will read it, when it goes. The editor used to put all four on one long
 * page and leave the writer to remember where they were. This rail names the
 * order, shows the one thing still missing at each stage, and moves the page
 * instead of hiding content: nothing is lost when a step is skipped.
 */
export type Stage = "write" | "design" | "preview" | "queue";

const STAGES: { key: Stage; label: string; detail: string; anchor: string }[] = [
  { key: "write", label: "Write", detail: "The words", anchor: "post-write" },
  { key: "design", label: "Design", detail: "Image and buttons", anchor: "post-design" },
  { key: "preview", label: "Preview", detail: "Read it as a phone", anchor: "post-preview" },
  { key: "queue", label: "Queue", detail: "Send or schedule", anchor: "post-queue" },
];

const ICONS = { write: PenLine, design: Sparkles, preview: Eye, queue: Clock3 };

export function PostFlow({
  characters,
  limit,
  hasImage,
  buttons,
  canPublish,
  schedule,
  save,
  words = 0,
}: {
  characters: number;
  limit: number;
  hasImage: boolean;
  buttons: number;
  canPublish: boolean;
  schedule?: { ready: boolean; note: string };
  /** "Saving…" / "Saved 4s ago" / "Autosave off" — the rail is where a writer
   *  looks when they want to know whether it is safe to close the tab. */
  save?: { state: "idle" | "saving" | "saved" | "error"; note: string };
  words?: number;
}) {
  const [active, setActive] = useState<Stage>("write");
  const [done, setDone] = useState<Record<Stage, boolean>>({
    write: false,
    design: false,
    preview: false,
    queue: false,
  });

  useEffect(() => {
    setDone((current) => ({
      ...current,
      write: characters > 0,
      design: hasImage || buttons > 0,
      queue: canPublish,
    }));
  }, [characters, hasImage, buttons, canPublish]);

  /* The rail follows the page: whichever stage is in front of the reader is
     the one that is lit. Scrolling is how people actually skip around, so the
     rail listens to it rather than to clicks. */
  useEffect(() => {
    const sections = STAGES.map((stage) => document.getElementById(stage.anchor)).filter(
      (node): node is HTMLElement => Boolean(node),
    );
    if (!sections.length || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        const match = STAGES.find((stage) => stage.anchor === visible.target.id);
        if (match) setActive(match.key);
      },
      { rootMargin: "-20% 0px -55% 0px", threshold: [0.05, 0.4, 0.8] },
    );
    sections.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  const firstMissing = STAGES.find((stage) => !done[stage.key])?.key;

  return (
    <nav className="post-flow" aria-label="Post workflow">
      <ol>
        {STAGES.map((stage, index) => {
          const Icon = ICONS[stage.key];
          const state = done[stage.key] ? "done" : stage.key === firstMissing ? "next" : "todo";
          return (
            <li key={stage.key}>
              <button
                type="button"
                data-active={active === stage.key}
                data-state={state}
                onClick={() => {
                  const node = document.getElementById(stage.anchor);
                  node?.scrollIntoView({ behavior: "smooth", block: "start" });
                  node?.focus({ preventScroll: true });
                }}
                aria-current={active === stage.key ? "step" : undefined}
              >
                <span className="post-flow-icon" aria-hidden>
                  {done[stage.key] ? <Check size={13} strokeWidth={3} /> : <Icon size={13} />}
                </span>
                <span className="post-flow-text">
                  <b>
                    {index + 1}. {stage.label}
                  </b>
                  <i>{stage.detail}</i>
                </span>
              </button>
              {index < STAGES.length - 1 ? (
                <ArrowRight className="post-flow-arrow" size={13} aria-hidden />
              ) : null}
            </li>
          );
        })}
      </ol>
      <div className="post-flow-meter">
        <span className="post-flow-count" data-over={characters > limit}>
          {characters}
          <i>/{limit}</i>
        </span>
        {words ? <span className="post-flow-words">{words} {words === 1 ? "word" : "words"}</span> : null}
        {save ? (
          <span className="post-flow-schedule" data-state={save.state} data-ready={schedule?.ready}>
            <Circle size={7} aria-hidden /> {save.note}
          </span>
        ) : schedule ? (
          <span className="post-flow-schedule" data-ready={schedule.ready}>
            <Circle size={7} aria-hidden /> {schedule.note}
          </span>
        ) : null}
      </div>
    </nav>
  );
}
