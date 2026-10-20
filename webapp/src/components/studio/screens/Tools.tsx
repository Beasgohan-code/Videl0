"use client";
import { useState } from "react";
import { textInsights, campaignLink } from "@/lib/creator-tools";
export default function Tools() {
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [source, setSource] = useState("telegram");
  const [medium, setMedium] = useState("social");
  const [campaign, setCampaign] = useState("");
  const [status, setStatus] = useState("");
  const stats = textInsights(text);
  let link = "",
    error = "";
  if (url)
    try {
      link = campaignLink(url, source, medium, campaign);
    } catch {
      error = "Use an http(s) URL without a username or password.";
    }
  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setStatus("Copied to clipboard");
    } catch {
      setStatus("Clipboard unavailable. Select and copy the result manually.");
    }
  }
  return (
    <main className="mx-auto max-w-5xl py-8">
      <p className="ios-caps text-[11px]">Small tools, better posts</p>
      <h1 className="ios-title mt-3">Creator Tools</h1>
      <p className="mt-3 text-sm text-indigo-100/50">
        Private by design. Your text and links are processed on this device.
      </p>
      <div className="mt-7 grid gap-5 lg:grid-cols-2">
        <section className="ios-card p-5">
          <h2 className="text-lg font-semibold">Caption & hashtag check</h2>
          <label className="mt-4 block text-sm">
            Your text
            <textarea
              className="ios-input mt-2 min-h-52"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste a caption or write something new…"
            />
          </label>
          <p className="mt-3 text-xs text-indigo-100/60">
            {stats.words} words · {stats.characters} characters ·{" "}
            {stats.telegramLength} Telegram units
          </p>
          <div className="mt-4 space-y-2 text-sm">
            {[
              ["Photo caption", 1024],
              ["Text post", 4096],
            ].map(([label, max]) => (
              <p
                key={label}
                className={
                  stats.telegramLength > Number(max)
                    ? "text-amber-200"
                    : "text-emerald-200"
                }
              >
                {label}: {Math.max(0, Number(max) - stats.telegramLength)}{" "}
                remaining
                {stats.telegramLength > Number(max)
                  ? ` · ${stats.telegramLength - Number(max)} over limit`
                  : ""}
              </p>
            ))}
          </div>
          <p className="mt-5 break-words text-sm text-indigo-200">
            {stats.hashtags.join(" ") || "Unique hashtags will appear here."}
          </p>
          <button
            disabled={!stats.hashtags.length}
            className="ios-btn ios-btn-glass mt-4 text-sm disabled:opacity-40"
            onClick={() => void copy(stats.hashtags.join(" "))}
          >
            Copy hashtags
          </button>
        </section>
        <section className="ios-card p-5">
          <h2 className="text-lg font-semibold">Campaign link builder</h2>
          <p className="mt-2 text-xs leading-5 text-indigo-100/50">
            Add tracking labels for your own analytics. No shortener, redirect
            or tracking service is used here.
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
                onChange={(e) =>
                  (set as (value: string) => void)(e.target.value)
                }
              />
            </label>
          ))}
          {error && <p className="mt-4 text-xs text-amber-200">{error}</p>}
          {link && (
            <>
              <textarea
                aria-label="Campaign URL"
                readOnly
                value={link}
                className="ios-input mt-4 min-h-24"
              />
              <button
                onClick={() => void copy(link)}
                className="ios-btn ios-btn-primary mt-4 text-sm"
              >
                Copy campaign URL
              </button>
            </>
          )}
        </section>
      </div>
      <p role="status" className="mt-4 text-sm text-indigo-200">
        {status}
      </p>
    </main>
  );
}
