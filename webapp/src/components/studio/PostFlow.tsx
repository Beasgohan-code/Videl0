"use client";
import { useState } from "react";
import { ArrowLeft, ArrowRight, Check, Circle, Clock3, Eye, PenLine, Sparkles } from "lucide-react";

/** A guided, four-page publishing flow. The draft stays in the parent while
 * each page shows just the controls needed for that step. */
export type Stage = "write" | "design" | "preview" | "queue";

const STAGES: { key: Stage; label: string; detail: string; anchor: string }[] = [
  { key: "write", label: "Write", detail: "The words", anchor: "post-write" },
  { key: "design", label: "Design", detail: "Image and buttons", anchor: "post-design" },
  { key: "preview", label: "Preview", detail: "Read it as a phone", anchor: "post-preview" },
  { key: "queue", label: "Publish", detail: "Send or schedule", anchor: "post-queue" },
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
  previewed = false,
  published = false,
  activeStage,
  onStageChange,
}: {
  characters: number;
  limit: number;
  hasImage: boolean;
  buttons: number;
  canPublish: boolean;
  schedule?: { ready: boolean; note: string };
  save?: { state: "idle" | "saving" | "saved" | "error"; note: string };
  words?: number;
  previewed?: boolean;
  published?: boolean;
  activeStage?: Stage;
  onStageChange?: (stage: Stage) => void;
}) {
  const [localActive, setLocalActive] = useState<Stage>("write");
  const active = activeStage ?? localActive;
  const done: Record<Stage, boolean> = {
    write: canPublish,
    design: hasImage || buttons > 0,
    preview: previewed,
    queue: published,
  };

  const change = (stage: Stage) => {
    setLocalActive(stage);
    onStageChange?.(stage);
  };
  const currentIndex = Math.max(0, STAGES.findIndex((stage) => stage.key === active));
  const previous = STAGES[currentIndex - 1];
  const next = STAGES[currentIndex + 1];
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
                onClick={() => change(stage.key)}
                aria-current={active === stage.key ? "step" : undefined}
                aria-label={`Step ${index + 1}: ${stage.label}${done[stage.key] ? ", complete" : ""}`}
              >
                <span className="post-flow-icon" aria-hidden>
                  {done[stage.key] ? <Check size={13} strokeWidth={3} /> : <Icon size={13} />}
                </span>
                <span className="post-flow-text">
                  <b>{index + 1}. {stage.label}</b>
                  <i>{stage.detail}</i>
                </span>
              </button>
              {index < STAGES.length - 1 ? <ArrowRight className="post-flow-arrow" size={13} aria-hidden /> : null}
            </li>
          );
        })}
      </ol>
      <div className="post-flow-meter">
        <span className="post-flow-count" data-over={characters > limit}>
          {characters.toLocaleString()}<i>/{limit.toLocaleString()}</i>
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
      <div className="post-flow-pager" aria-label={`Step ${currentIndex + 1} of ${STAGES.length}`}>
        {previous ? (
          <button type="button" className="post-flow-page-button post-flow-previous" onClick={() => change(previous.key)}>
            <ArrowLeft size={14} aria-hidden /> Back
          </button>
        ) : <span className="post-flow-step-count">Start</span>}
        <span className="post-flow-step-count">Step {currentIndex + 1} of {STAGES.length}</span>
        {next ? (
          <button type="button" className="post-flow-page-button post-flow-continue" onClick={() => change(next.key)}>
            Continue to {next.label} <ArrowRight size={14} aria-hidden />
          </button>
        ) : (
          <span className="post-flow-step-count">Final step</span>
        )}
      </div>
      <span className="sr-only" aria-live="polite">Step {currentIndex + 1} of {STAGES.length}: {STAGES[currentIndex]?.label}</span>
      <span className="sr-only">{canPublish ? "Post content is ready for review." : "Add text or media before publishing."}</span>
    </nav>
  );
}
