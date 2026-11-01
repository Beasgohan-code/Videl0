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
  Music2,
  Check,
  Sparkles,
} from "lucide-react";
import { useTelegram } from "@/components/TelegramProvider";
import { GAME_ART } from "@/lib/arcade";
import { POST_ASSETS } from "@/lib/post-assets";
import { useStudio } from "../StudioProvider";
import { useRef } from "react";
import { useScreenMotion } from "../useScreenMotion";
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
  const rootRef = useRef<HTMLElement>(null);
  useScreenMotion(rootRef, "guest-home");
  if (authenticated === true) return <OwnerHome />;
  return (
    <main ref={rootRef} className="ios-page home-page">
      <section className="home-hero" aria-labelledby="home-title">
        <span className="home-hero-orb home-hero-orb-one" aria-hidden="true" />
        <span className="home-hero-orb home-hero-orb-two" aria-hidden="true" />
        <div className="home-hero-copy">
          <p data-screen-intro className="home-eyebrow"><span aria-hidden="true" /> YOUR CREATIVE SPACE <span className="home-eyebrow-divider" /> FREE TO START</p>
          <h1 id="home-title" data-screen-intro className="home-title">
            Make something <span>worth sharing.</span>
          </h1>
          <p data-screen-intro className="home-description">
            Write polished Telegram posts, build custom visuals and keep your ideas together.
            <span> Free to create. No sign-in needed.</span>
          </p>
          <div data-screen-intro className="home-actions">
            <button onClick={() => open("post")} className="ios-btn ios-btn-primary home-primary-action">
              <Palette size={17} aria-hidden /> Open Post Studio <ArrowUpRight size={17} aria-hidden />
            </button>
            <button onClick={() => open("guide")} className="ios-btn ios-btn-glass">
              <BookOpen size={16} aria-hidden /> Browse the command guide
            </button>
          </div>
          <div data-screen-intro className="home-trust-row" aria-label="Studio features">
            <span><Check size={13} aria-hidden /> Private by design</span>
            <span><Sparkles size={13} aria-hidden /> Ready-to-use templates</span>
            <button onClick={() => open("arcade")}><Gamepad2 size={13} aria-hidden /> Play the arcade <ArrowUpRight size={12} aria-hidden /></button>
            <button onClick={() => open("auth")}><Music2 size={13} aria-hidden /> Videl Music <ArrowUpRight size={12} aria-hidden /></button>
          </div>
        </div>
        <div className="home-hero-art" aria-hidden="true">
          <div className="home-orbit home-orbit-one" />
          <div className="home-orbit home-orbit-two" />
          <div className="home-art-disc"><span>V</span><i /><b /></div>
          <div className="home-art-caption"><span>VIDEL STUDIO</span><small>CREATE · SHARE · PLAY</small></div>
          <div className="home-art-chip home-art-chip-top"><Sparkles size={13} /> Your next idea</div>
          <div className="home-art-chip home-art-chip-bottom"><span /> All systems creative</div>
        </div>
      </section>

      <button
        onClick={() => open("arcade")}
        className="arcade-home-card mt-6"
        data-screen-stagger
        aria-label="Open the arcade"
      >
        <span className="arcade-home-dice" aria-hidden>
          {/* The table itself, at thumbnail size: the same art the lobby uses. */}
          <img src={GAME_ART.ludo} alt="" loading="lazy" decoding="async" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="arcade-home-title">The arcade is open</span>
          <span className="arcade-home-copy">
            Ten boards, up to six chairs and live voice: Chinese Checkers, Dots & Boxes,
            Yacht, Ludo, Chess, Checkers, and the quick classics.
            Send the six-character code or the invite link; the server keeps the
            board.
          </span>
          <span className="arcade-home-games" aria-hidden>
            <i>✦ Chinese Checkers</i>
            <i>⠿ Dots &amp; Boxes</i>
            <i>🎲 Yacht</i>
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
              data-screen-stagger
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
            data-screen-stagger
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
