"use client";
import dynamic from "next/dynamic";
import { Palette, FileText, LockKeyhole, ArrowUpRight } from "lucide-react";
import { useTelegram } from "@/components/TelegramProvider";
import { useStudio } from "../StudioProvider";
const OwnerHome = dynamic(() => import("./OwnerHome"));
export default function Home() {
  const { authenticated } = useTelegram();
  const { open } = useStudio();
  if (authenticated === true) return <OwnerHome />;
  return (
    <main className="mx-auto max-w-6xl py-10 sm:py-16">
      <p className="ios-caption2">YOUR CREATIVE SPACE</p>
      <h1 className="mt-4 max-w-2xl text-4xl font-semibold tracking-tight sm:text-6xl">
        Make something worth sharing.
      </h1>
      <p className="mt-5 max-w-xl text-base leading-7 text-indigo-100/55">
        Write polished Telegram posts, build custom visuals and keep your ideas
        together. Free to create. No sign-in needed.
      </p>
      <button
        onClick={() => open("post")}
        className="ios-btn ios-btn-primary mt-7"
      >
        Open Post Studio <ArrowUpRight size={18} />
      </button>
      <section className="mt-10 grid gap-4 sm:grid-cols-2">
        {[
          {
            tab: "post" as const,
            icon: Palette,
            title: "Post & image studio",
            body: "Format selected text, customize 20 editable layouts, save local drafts and export your designs.",
          },
          {
            tab: "tools" as const,
            icon: FileText,
            title: "Everyday creator tools",
            body: "Check caption limits, collect hashtags and build campaign links. Everything runs in your browser.",
          },
        ].map((item) => (
          <button
            key={item.tab}
            onClick={() => open(item.tab)}
            className="ios-card p-6 text-left transition hover:border-indigo-300/30"
          >
            <item.icon className="text-indigo-300" size={27} />
            <h2 className="mt-5 text-lg font-semibold">{item.title}</h2>
            <p className="mt-3 text-sm leading-6 text-indigo-100/50">
              {item.body}
            </p>
          </button>
        ))}
      </section>
      <p className="mt-8 flex items-center gap-2 text-xs text-indigo-100/40">
        <LockKeyhole size={14} /> Your drafts stay on this device. Creating and
        exporting does not send anything to Telegram.
      </p>
    </main>
  );
}
