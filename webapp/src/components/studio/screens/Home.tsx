"use client";
import dynamic from "next/dynamic";
import {
  Palette,
  FileText,
  LockKeyhole,
  ArrowUpRight,
  BookOpen,
  Images,
  Gamepad2,
} from "lucide-react";
import { useTelegram } from "@/components/TelegramProvider";
import { GAME_ART } from "@/lib/arcade";
import { POST_ASSETS } from "@/lib/post-assets";
import { useStudio } from "../StudioProvider";
const OwnerHome = dynamic(() => import("./OwnerHome"));

// A stable, curated slice of the generated library. Falls back to the first
// covers if the asset engine is ever re-run with different identifiers.
const featured = ["promo", "studio", "manifesto"]
  .map((id) => POST_ASSETS.find((asset) => asset.id === id))
  .filter((asset): asset is (typeof POST_ASSETS)[number] => Boolean(asset));
const showcase = (featured.length === 3
  ? featured
  : POST_ASSETS.filter((asset) => asset.aspect === "16:9").slice(0, 3)
).slice(0, 3);

const coverCount = POST_ASSETS.filter((asset) => asset.aspect === "16:9").length;

export default function Home() {
  const { authenticated } = useTelegram();
  const { open } = useStudio();
  if (authenticated === true) return <OwnerHome />;
  return (
    <main className="ios-page">
      <p className="ios-caps text-[12px] text-indigo-200/45">Your creative space</p>
      <h1 className="mt-4 max-w-2xl text-4xl font-semibold tracking-tight sm:text-6xl">
        Make something worth sharing.
      </h1>
      <p className="mt-5 max-w-xl text-base leading-7 text-indigo-100/55">
        Write polished Telegram posts, build custom visuals and keep your ideas
        together. Free to create. No sign-in needed.
      </p>
      <div className="mt-7 flex flex-wrap items-center gap-3">
        <button onClick={() => open("post")} className="ios-btn ios-btn-primary">
          Open Post Studio <ArrowUpRight size={18} aria-hidden />
        </button>
        <button onClick={() => open("guide")} className="ios-btn ios-btn-glass">
          <BookOpen size={16} aria-hidden /> Browse the command guide
        </button>
        <button onClick={() => open("arcade")} className="ios-btn ios-btn-glass">
          <Gamepad2 size={16} aria-hidden /> Play in the arcade
        </button>
      </div>

      <button
        onClick={() => open("arcade")}
        className="arcade-home-card mt-6"
        aria-label="Open the arcade"
      >
        <span className="arcade-home-dice" aria-hidden>
          {/* The table itself, at thumbnail size: the same art the lobby uses. */}
          <img src={GAME_ART.ludo} alt="" loading="lazy" decoding="async" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="arcade-home-title">The arcade is open</span>
          <span className="arcade-home-copy">
            Seven boards, real chairs and live voice: Chess, Checkers, Ludo for
            two to four, Five in a Row, Connect Four, Reversi and Tic-tac-toe.
            Send the six-character code or the invite link; the server keeps the
            board.
          </span>
          <span className="arcade-home-games" aria-hidden>
            <i>♞ Chess</i>
            <i>♛ Checkers</i>
            <i>◈ Ludo</i>
            <i>⬤ Five in a Row</i>
            <i>◍ Connect Four</i>
            <i>◐ Reversi</i>
            <i>✕ Tic-tac-toe</i>
          </span>
        </span>
        <ArrowUpRight size={18} aria-hidden className="arcade-home-arrow" />
      </button>

      <section
        aria-label="Original image library"
        className="mt-12 rounded-3xl border border-indigo-300/10 bg-indigo-300/[0.03] p-4 sm:p-5"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 px-1">
          <p className="ios-caps flex items-center gap-2 text-[11px] text-indigo-100/50">
            <Images size={14} aria-hidden /> Made here, not stock
          </p>
          <span className="mono text-[10px] text-indigo-100/35">
            {coverCount} covers · {POST_ASSETS.length} images
          </span>
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {showcase.map((asset) => (
            <button
              key={asset.id}
              onClick={() => open("post")}
              className="ios-card-interactive group overflow-hidden rounded-2xl border border-white/10"
              aria-label={`Open Post Studio to use “${asset.title}”`}
            >
              <span className="block overflow-hidden">
                <img
                  src={asset.file}
                  alt=""
                  width={1200}
                  height={675}
                  loading="lazy"
                  decoding="async"
                  className="aspect-video w-full object-cover transition duration-500 group-hover:scale-[1.035]"
                />
              </span>
              <span className="flex items-center justify-between gap-2 bg-[#0b1023] px-3 py-2.5">
                <span className="ios-caps text-[10px] text-indigo-100/55">
                  {asset.category}
                </span>
                <span className="text-[11px] text-indigo-100/35">16:9</span>
              </span>
            </button>
          ))}
        </div>
        <p className="mt-3 px-1 text-[11px] leading-5 text-indigo-100/35">
          Every image is generated locally by the bundled artwork engine — open one,
          restyle it and export. Your own uploads never leave this browser.
        </p>
      </section>

      <section className="mt-6 grid gap-4 sm:grid-cols-3">
        {[
          {
            tab: "post" as const,
            icon: Palette,
            title: "Post & image studio",
            body: "Format selected text, customize editable layouts, save drafts and export your designs.",
          },
          {
            tab: "tools" as const,
            icon: FileText,
            title: "Everyday creator tools",
            body: "Check caption limits, collect hashtags and build campaign links in one place.",
          },
          {
            tab: "guide" as const,
            icon: BookOpen,
            title: "Every command, explained",
            body: "Search the full bot manual, copy a command and see where it works before you send it.",
          },
        ].map((item) => (
          <button
            key={item.tab}
            onClick={() => open(item.tab)}
            className="ios-card ios-card-interactive p-6"
          >
            <item.icon className="text-indigo-300" size={27} aria-hidden />
            <h2 className="mt-5 text-lg font-semibold">{item.title}</h2>
            <p className="mt-3 text-sm leading-6 text-indigo-100/50">{item.body}</p>
          </button>
        ))}
      </section>
      <p className="mt-8 flex items-center gap-2 text-xs text-indigo-100/40">
        <LockKeyhole size={14} aria-hidden /> Your drafts stay on this device. Creating and
        exporting does not send anything to Telegram.
      </p>
    </main>
  );
}
