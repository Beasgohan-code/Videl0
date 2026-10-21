"use client";
import { useMemo, useState } from "react";
import {
  Check,
  Clipboard,
  Code2,
  Eye,
  FileText,
  Link2,
  Sparkles,
  Trash2,
} from "lucide-react";
import { campaignLink, textInsights } from "@/lib/creator-tools";
import { markdownToTelegram } from "@/lib/markdown-telegram";
import { previewHtml } from "@/lib/telegram-format";
import { Callout, PageHeader } from "../ui";

const EXAMPLE = `## Launch day
**Videl 2.0** is live — *finally*.

> One workspace for posts, commands and groups.

- 54 original images
- A full command guide
- Markdown in, Telegram HTML out

Read the notes: [videl.studio](https://videl-studio.vercel.app)`;

export default function Tools() {
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [source, setSource] = useState("telegram");
  const [medium, setMedium] = useState("social");
  const [campaign, setCampaign] = useState("");
  const [status, setStatus] = useState("");
  const [markdown, setMarkdown] = useState("");
  const [view, setView] = useState<"html" | "preview">("html");
  const [copied, setCopied] = useState("");

  const stats = textInsights(text);
  let link = "",
    error = "";
  if (url)
    try {
      link = campaignLink(url, source, medium, campaign);
    } catch {
      error = "Use an http(s) URL without a username or password.";
    }

  const telegramHtml = useMemo(() => markdownToTelegram(markdown), [markdown]);

  async function copy(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      setStatus(`${label} copied to clipboard`);
      setCopied(label);
      window.setTimeout(() => setCopied((current) => (current === label ? "" : current)), 1600);
    } catch {
      setStatus("Clipboard unavailable. Select and copy the result manually.");
    }
  }

  return (
    <main className="ios-page">
      <PageHeader
        eyebrow="Small tools, better posts"
        title="Creator tools"
        subtitle="Private by design. Your text, links and Markdown are processed in this browser and never uploaded."
        actions={
          <span className="ios-pill ios-pill-green">
            <Sparkles size={12} aria-hidden /> Runs locally
          </span>
        }
      />

      <div className="mt-7 grid gap-5 lg:grid-cols-2">
        <section className="ios-card p-5">
          <div className="flex items-center gap-2">
            <FileText size={17} className="text-indigo-300" />
            <h2 className="text-lg font-semibold">Caption &amp; hashtag check</h2>
          </div>
          <label className="mt-4 block text-sm">
            Your text
            <textarea
              className="ios-input mt-2 min-h-52"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Paste a caption or write something new…"
            />
          </label>
          <p className="mt-3 text-xs text-[var(--ios-label-secondary)]">
            {stats.words} words · {stats.characters} characters ·{" "}
            {stats.telegramLength} Telegram units
          </p>
          <div className="mt-4 space-y-2 text-sm">
            {[
              ["Photo caption", 1024],
              ["Text post", 4096],
            ].map(([label, max]) => {
              const over = stats.telegramLength > Number(max);
              return (
                <p key={label} className={over ? "text-amber-200" : "text-emerald-200"}>
                  {label}: {Math.max(0, Number(max) - stats.telegramLength)} remaining
                  {over ? ` · ${stats.telegramLength - Number(max)} over limit` : ""}
                </p>
              );
            })}
          </div>
          <p className="mt-5 break-words text-sm text-indigo-200">
            {stats.hashtags.join(" ") || "Unique hashtags will appear here."}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              disabled={!stats.hashtags.length}
              className="ios-btn ios-btn-glass text-sm disabled:opacity-40"
              onClick={() => void copy(stats.hashtags.join(" "), "Hashtags")}
            >
              <Clipboard size={14} /> Copy hashtags
            </button>
            <button
              disabled={!text}
              className="ios-btn ios-btn-glass text-sm disabled:opacity-40"
              onClick={() => {
                setText("");
                setStatus("Caption cleared");
              }}
            >
              <Trash2 size={14} /> Clear
            </button>
          </div>
        </section>

        <section className="ios-card p-5">
          <div className="flex items-center gap-2">
            <Link2 size={17} className="text-indigo-300" />
            <h2 className="text-lg font-semibold">Campaign link builder</h2>
          </div>
          <p className="mt-2 text-xs leading-5 text-[var(--ios-label-secondary)]">
            Add tracking labels for your own analytics. No shortener, redirect or
            tracking service is used here.
          </p>
          {[
            ["Website URL", url, setUrl],
            ["Source", source, setSource],
            ["Medium", medium, setMedium],
            ["Campaign", campaign, setCampaign],
          ].map(([label, value, set]) => (
            <label key={String(label)} className="mt-4 block text-sm">
              {String(label)}
              <input
                className="ios-input mt-2"
                value={String(value)}
                onChange={(event) =>
                  (set as (value: string) => void)(event.target.value)
                }
              />
            </label>
          ))}
          {error && <Callout tone="warn" className="mt-4">{error}</Callout>}
          {link && (
            <>
              <textarea
                aria-label="Campaign URL"
                readOnly
                value={link}
                className="ios-input mt-4 min-h-24"
              />
              <button
                onClick={() => void copy(link, "Campaign URL")}
                className="ios-btn ios-btn-primary mt-4 text-sm"
              >
                {copied === "Campaign URL" ? <Check size={15} /> : <Clipboard size={15} />}
                Copy campaign URL
              </button>
            </>
          )}
        </section>
      </div>

      <section className="ios-card mt-5 p-5" aria-labelledby="markdown-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Code2 size={17} className="text-indigo-300" />
            <h2 id="markdown-title" className="text-lg font-semibold">
              Markdown → Telegram HTML
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setMarkdown(EXAMPLE)}
              className="ios-btn ios-btn-glass text-xs"
            >
              <Sparkles size={13} /> Load example
            </button>
            <div className="flex rounded-full border border-white/10 bg-white/[0.03] p-1">
              <button
                onClick={() => setView("html")}
                aria-pressed={view === "html"}
                className={`ios-chip !border-0 !py-1.5 text-[11px] ${view === "html" ? "ios-chip-active" : ""}`}
              >
                <Code2 size={12} /> HTML
              </button>
              <button
                onClick={() => setView("preview")}
                aria-pressed={view === "preview"}
                className={`ios-chip !border-0 !py-1.5 text-[11px] ${view === "preview" ? "ios-chip-active" : ""}`}
              >
                <Eye size={12} /> Preview
              </button>
            </div>
          </div>
        </div>
        <p className="mt-2 max-w-2xl text-xs leading-5 text-[var(--ios-label-secondary)]">
          Write once, paste into any Videl composer. Bold, italics, strike, spoilers,
          code, quotes, links and headings are converted; unsafe links stay as plain
          text instead of becoming clickable.
        </p>

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <label className="block text-sm">
            Markdown
            <textarea
              className="ios-input mt-2 min-h-64 font-mono text-xs leading-6"
              value={markdown}
              onChange={(event) => setMarkdown(event.target.value)}
              placeholder={"**Bold** and *italic*\n> a quote\n[link](https://example.com)"}
              spellCheck={false}
            />
          </label>
          <div className="flex flex-col">
            <div className="flex items-center justify-between text-sm">
              <span>{view === "html" ? "Telegram HTML" : "Rendered preview"}</span>
              <span className="mono text-[10px] text-[var(--ios-label-tertiary)]">
                {telegramHtml.length} chars
              </span>
            </div>
            {view === "html" ? (
              <textarea
                aria-label="Telegram HTML output"
                readOnly
                value={telegramHtml}
                className="ios-input mt-2 min-h-64 flex-1 font-mono text-xs leading-6"
                placeholder="Converted HTML appears here…"
              />
            ) : (
              <div className="mt-2 min-h-64 flex-1 rounded-xl border border-white/10 bg-[#0f1524] p-4">
                {telegramHtml ? (
                  <div
                    className="telegram-rich max-w-[95%] break-words rounded-2xl rounded-tl-md bg-[#182533] px-3.5 py-3 text-sm leading-6 text-indigo-50/90"
                    dangerouslySetInnerHTML={{ __html: previewHtml(telegramHtml) }}
                  />
                ) : (
                  <p className="text-xs italic text-[var(--ios-label-tertiary)]">
                    Write Markdown on the left to see the Telegram result.
                  </p>
                )}
                <p className="mt-3 text-[10px] text-[var(--ios-label-tertiary)]">
                  Preview only · Telegram applies the final layout.
                </p>
              </div>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                disabled={!telegramHtml}
                onClick={() => void copy(telegramHtml, "Telegram HTML")}
                className="ios-btn ios-btn-primary text-sm disabled:opacity-40"
              >
                {copied === "Telegram HTML" ? <Check size={15} /> : <Clipboard size={15} />}
                Copy HTML
              </button>
              <button
                disabled={!markdown}
                onClick={() => {
                  setMarkdown("");
                  setView("html");
                }}
                className="ios-btn ios-btn-glass text-sm disabled:opacity-40"
              >
                <Trash2 size={14} /> Clear
              </button>
            </div>
          </div>
        </div>
      </section>

      {status && <Callout tone="success" className="mt-4" live>{status}</Callout>}
    </main>
  );
}
