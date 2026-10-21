"use client";
import { useTelegram } from "@/components/TelegramProvider";
import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  Check,
  Clipboard,
  Copy,
  Eye,
  RefreshCw,
  Send,
  Trash2,
} from "lucide-react";
import {ScheduledPosts} from "@/components/studio/ScheduledPosts";
import { ImageComposer } from "@/components/studio/ImageComposer";
import { PostAssetLibrary } from "@/components/studio/PostAssetLibrary";
import {postChecks,VERSION_KEY} from "@/lib/studio-drafts";
import { visibleLength, plainPostText } from "@/lib/telegram-format";
import { RichEditor } from "@/components/editor/RichEditor";
import { ButtonBuilder, BtnRow } from "@/components/editor/ButtonBuilder";
import { ChannelPreview } from "@/components/channel/Preview";
import { PostFlow } from "@/components/studio/PostFlow";

import {
  PostDraft as Draft,
  DRAFT_KEY,
  RECOVERY_KEY,
  draftDocument,
  importDraftDocument,
  parseDrafts,
  parseDraft,
  copyDraft,
} from "@/lib/post-drafts";
type Result = { ok: boolean; message: string };
const templates = [
  {
    title: "Community update",
    tag: "Announcement",
    text: "<b>Community update</b>\n\nHere’s what’s new this week:\n• Add your first update\n• Add your second update\n\nThanks for being part of our community!",
  },
  {
    title: "Event invitation",
    tag: "Event",
    text: "<b>You’re invited!</b>\n\n<b>What:</b> Your event name\n<b>When:</b> Add date and timezone\n<b>Where:</b> Add meeting details\n\nSave the date — we’d love to see you there.",
  },
  {
    title: "Welcome message",
    tag: "Community",
    text: "<b>Welcome to the community!</b>\n\nIntroduce yourself, explore the pinned messages and make yourself at home.\n\nPlease keep things respectful. We’re glad you’re here!",
  },
];
export default function ChannelStudio() {
  const { authenticated } = useTelegram();
  const isOwner = authenticated === true;
  const [showAssets, setShowAssets] = useState(false);
  const [showCovers, setShowCovers] = useState(false);
  const [localImage, setLocalImage] = useState<File | null>(null);
  useEffect(() => {
    if (!localImage) return;
    const url = URL.createObjectURL(localImage);
    setMediaUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [localImage]);
  const lastSent = useRef("");
  const sending = useRef(false);
  const [reviewed, setReviewed] = useState(false);
  /**
   * Undo is a stack, not an apology. Every action that throws work away — a
   * new post, opening a draft, importing a file — pushes the outgoing state
   * here first, so the notice can walk back one step at a time instead of
   * stopping the writer with a confirm dialog.
   */
  type Snapshot = {
    reason: string;
    text: string;
    mediaUrl: string;
    localImage: File | null;
    buttons: BtnRow[];
    chatId: string;
    at: number;
  };
  const [undo, setUndo] = useState<Snapshot[]>([]);
  const [showTemplates, setShowTemplates] = useState(false);

  const [chatId, setChatId] = useState("");
  const [text, setText] = useState("");
  const [parseMode, setParseMode] = useState<"HTML" | "Markdown">("HTML");
  const [mediaUrl, setMediaUrl] = useState("");
  const [buttons, setButtons] = useState<BtnRow[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [versions,setVersions]=useState<Draft[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [lightPreview, setLightPreview] = useState(false);
  useEffect(() => {
    setReviewed(false);
  }, [chatId, text, mediaUrl, parseMode, buttons]);
  const [recovery, setRecovery] = useState<Draft | null>(null);
  const [storageReady, setStorageReady] = useState(false);
  const [autoStatus, setAutoStatus] = useState("");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [savedAt, setSavedAt] = useState(0);
  // A "saved 8s ago" that never moves is a lie the moment it is read.
  const [, setClock] = useState(0);
  useEffect(() => {
    if (!savedAt) return;
    const timer = window.setInterval(() => setClock((value) => value + 1), 5000);
    return () => window.clearInterval(timer);
  }, [savedAt]);
  useEffect(() => {
    try {
      setDrafts(parseDrafts(localStorage.getItem(DRAFT_KEY) || "[]"));
      setVersions(parseDrafts(localStorage.getItem(VERSION_KEY) || "[]"));
      const saved = localStorage.getItem(RECOVERY_KEY);
      if (saved) setRecovery(parseDraft(JSON.parse(saved)));
    } catch {
      setAutoStatus("Local recovery unavailable; save a copy before leaving.");
    }
    setStorageReady(true);
  }, []);
  useEffect(() => {
    if (!storageReady || recovery) return;
    const timer = setTimeout(() => {
      try {
        if (text.trim() || mediaUrl.startsWith("https://")) {
          localStorage.setItem(
            RECOVERY_KEY,
            JSON.stringify({
              id: "autosave",
              chatId,
              text,
              parseMode,
              mediaUrl: localImage ? "" : mediaUrl,
              buttons,
              savedAt: new Date().toISOString(),
            }),
          );
          setAutoStatus(
            localImage
              ? "Text autosaved · attached image is session-only"
              : "Text and links autosaved on this device",
          );
          setSaveState("saved");
          setSavedAt(Date.now());
        } else {
          localStorage.removeItem(RECOVERY_KEY);
          setAutoStatus("");
        }
      } catch {
        setAutoStatus("Autosave unavailable. Copy your text before leaving.");
      }
    }, 600);
    return () => clearTimeout(timer);
  }, [
    chatId,
    text,
    parseMode,
    mediaUrl,
    buttons,
    localImage,
    storageReady,
    recovery,
  ]);
  useEffect(() => {
    if (!localImage && !busy) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [localImage, busy]);
  function persistDrafts(next: Draft[]) {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(next));
      setDrafts(next);
      return true;
    } catch {
      setResult({
        ok: false,
        message: "Browser storage is full; changes to drafts were not saved.",
      });
      return false;
    }
  }
  function pushUndo(reason: string) {
    if (!text.trim() && !localImage && !mediaUrl) return;
    const snapshot: Snapshot = {
      reason,
      text,
      mediaUrl,
      localImage,
      buttons,
      chatId,
      at: Date.now(),
    };
    setUndo((stack) => [...stack, snapshot].slice(-5));
  }
  function undoLast() {
    const snapshot = undo[undo.length - 1];
    if (!snapshot) return;
    setRecovery(null);
    setText(snapshot.text);
    setMediaUrl(snapshot.mediaUrl);
    setLocalImage(snapshot.localImage);
    setButtons(snapshot.buttons);
    setChatId(snapshot.chatId);
    setUndo((stack) => stack.slice(0, -1));
    setResult({ ok: true, message: "Put back the previous post." });
  }

  /* ── keyboard ─────────────────────────────────────────────────────────────
     Two shortcuts, both borrowed from the editors people already use:
     ⌘/Ctrl+S keeps a draft, ⌘/Ctrl+Enter publishes. Esc dismisses the undo
     notice without restoring anything. Typing inside a field is never
     intercepted except for those two combinations, so undo/redo keep working
     in the rich editor. */
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const command = event.metaKey || event.ctrlKey;
      if (command && event.key.toLowerCase() === "s") {
        event.preventDefault();
        saveDraft();
        return;
      }
      if (command && event.key === "Enter") {
        event.preventDefault();
        if (isOwner && reviewed && !busy) void sendPost();
        return;
      }
      if (event.key === "Escape") setUndo((stack) => (stack.length ? [] : stack));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function saveDraft() {
    if (localImage) {
      setResult({
        ok: false,
        message:
          "Download your image to keep it. Text-only recovery is autosaved; named drafts require an image URL or no attached image.",
      });
      return;
    }
    if (!text.trim() && !mediaUrl.trim()) {
      setResult({
        ok: false,
        message: "Add post text or a media URL before saving a draft.",
      });
      return;
    }
    const draft: Draft = {
      id: crypto.randomUUID(),
      chatId: chatId.trim(),
      text,
      parseMode,
      mediaUrl: mediaUrl.trim(),
      buttons: JSON.parse(JSON.stringify(buttons)),
      savedAt: new Date().toISOString(),
    };
    if (persistDrafts([draft, ...drafts].slice(0, 20)))
      setResult({ ok: true, message: "Draft saved in this browser only." });
  }
  /** Keep the post exactly as it is and start a second, separate copy of it. */
  function duplicatePost() {
    if (localImage) {
      setResult({
        ok: false,
        message:
          "Download the attached image first: a copy can carry text, links and buttons, not a local file.",
      });
      return;
    }
    if (!text.trim() && !mediaUrl.trim() && !buttons.length) {
      setResult({ ok: false, message: "Write something before duplicating it." });
      return;
    }
    const draft: Draft = {
      id: crypto.randomUUID(),
      chatId: isOwner ? chatId.trim() : "",
      text,
      parseMode,
      mediaUrl: mediaUrl.trim(),
      buttons: JSON.parse(JSON.stringify(buttons)),
      savedAt: new Date().toISOString(),
    };
    if (persistDrafts([draft, ...drafts].slice(0, 20))) {
      setResult({
        ok: true,
        message: "A copy is in your drafts. Edit this one freely; the copy stays as it was.",
      });
    }
  }

  function copySavedDraft(draft: Draft) {
    if (persistDrafts([copyDraft(draft), ...drafts].slice(0, 20))) {
      setResult({ ok: true, message: "Draft copied. It has its own name and date now." });
    }
  }

  function saveVersion(){
    if(!text.trim()&&!mediaUrl&&!buttons.length)return;
    const version:Draft={id:crypto.randomUUID(),chatId:isOwner?chatId:"",text,parseMode:"HTML",mediaUrl:localImage?"":mediaUrl,buttons:JSON.parse(JSON.stringify(buttons)),savedAt:new Date().toISOString()};
    const next=[version,...versions].slice(0,20);
    try{localStorage.setItem(VERSION_KEY,JSON.stringify(next));setVersions(next);setResult({ok:true,message:"Version saved locally. Local image files are not included."})}catch{setResult({ok:false,message:"Version not saved: browser storage unavailable."})}
  }
  function restoreDraft(draft: Draft) {
    pushUndo("Opened a saved draft");
    setRecovery(null);
    setLocalImage(null);
    setChatId(draft.chatId);
    setText(draft.text);
    setParseMode("HTML");
    setMediaUrl(draft.mediaUrl);
    setButtons(draft.buttons || []);
    setResult({ ok: true, message: "Draft restored." });
  }
  async function sendPost() {
    if (!isOwner || sending.current || !reviewed) return;
    if ((localImage || mediaUrl.trim()) && visibleLength(text) > 1024) {
      setResult({
        ok: false,
        message:
          "Image captions must be 1,024 characters or fewer. Shorten the text or remove the image.",
      });
      return;
    }
    if (!chatId.trim()) {
      setResult({
        ok: false,
        message: "Enter a numeric Telegram chat ID or @channel username.",
      });
      return;
    }
    if (!text.trim() && !mediaUrl.trim()) {
      setResult({ ok: false, message: "A post needs text, media, or both." });
      return;
    }
    if (visibleLength(text) > 4096) {
      setResult({
        ok: false,
        message: "Post text must be 4,096 characters or fewer.",
      });
      return;
    }
    const fingerprint = JSON.stringify([
      chatId.trim(),
      text,
      localImage
        ? [localImage.name, localImage.size, localImage.lastModified]
        : mediaUrl,
      buttons,
    ]);
    if (
      lastSent.current === fingerprint &&
      !window.confirm(
        "This exact post was already sent successfully. Publish it again?",
      )
    )
      return;
    sending.current = true;
    setBusy(true);
    setResult(null);
    try {
      let payload: BodyInit;
      let headers: Record<string, string> = {};
      if (localImage) {
        const form = new FormData();
        form.set("image", localImage, localImage.name);
        form.set("chat_id", chatId.trim());
        form.set("text", text);
        form.set("parse_mode", "HTML");
        if (buttons.length) form.set("buttons", JSON.stringify(buttons));
        payload = form;
      } else {
        headers = { "Content-Type": "application/json" };
        payload = JSON.stringify({
          chat_id: chatId.trim(),
          text,
          parse_mode: parseMode,
          media_url: mediaUrl.trim() || undefined,
          buttons: buttons.length ? JSON.stringify(buttons) : undefined,
        });
      }
      const response = await fetch("/api/channel", {
        method: "POST",
        headers,
        body: payload,
        signal: AbortSignal.timeout(35000),
      });
      const data = await response.json();
      if (!response.ok || !data.ok)
        throw new Error(data.error || "Telegram rejected the post");
      lastSent.current = fingerprint;
      setResult({
        ok: true,
        message: `Telegram accepted the post · message ${data.message_id} · chat ${data.chat_id}`,
      });
    } catch (error: any) {
      setResult({
        ok: false,
        message:
          error instanceof TypeError ||
          error instanceof SyntaxError ||
          error?.name === "TimeoutError"
            ? "Delivery could not be confirmed. Check Telegram before retrying to avoid duplicates."
            : error.message ||
              "Delivery could not be confirmed. Check Telegram before retrying to avoid duplicates.",
      });
    } finally {
      sending.current = false;
      setBusy(false);
      setReviewed(false);
    }
  }
  const hasImage = Boolean(localImage || mediaUrl.trim());
  const limit = hasImage ? 1024 : 4096;
  const remaining = limit - visibleLength(text);
  const previewTheme = lightPreview ? "light" : "dark";
  return (
    <main className="post-workspace mx-auto max-w-7xl py-5 sm:py-8">
      <header className="ios-page-header items-center">
        <div>
          <p className="ios-caption2">VIDEL · PUBLISHING</p>
          <h1 className="mt-2 ios-title">Post Studio</h1>
          <p className="mt-1 ios-subheadline">
            {isOwner
              ? "Create, preview and publish updates to your community."
              : "Write, design and export your next Telegram post. No sign-in required."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            disabled={busy}
            onClick={() => {
              // Nothing is lost: the outgoing post is kept in memory for a
              // moment, and the notice under the header puts it back. A modal
              // asking "are you sure" is a wall, not a safety net.
              pushUndo("Started a new post");
              setRecovery(null);
              setChatId("");
              setText("");
              setLocalImage(null);
              setMediaUrl("");
              setButtons([]);
              setResult(null);
            }}
            className="ios-btn ios-btn-glass text-sm"
          >
            <RefreshCw size={15} aria-hidden /> New post
          </button>
          <button
            disabled={busy}
            onClick={duplicatePost}
            className="ios-btn ios-btn-glass text-sm"
            title="Keep this post and start a second copy"
          >
            <Copy size={15} aria-hidden /> Duplicate
          </button>
          <button disabled={busy} className="ios-btn ios-btn-glass text-sm" onClick={() => {
            const draft:Draft={id:crypto.randomUUID(),chatId:isOwner?chatId:"",text,parseMode:"HTML",mediaUrl:localImage?"":mediaUrl,buttons,savedAt:new Date().toISOString()};
            try{const url=URL.createObjectURL(new Blob([draftDocument(draft)],{type:"application/json"}));const anchor=document.createElement("a");anchor.href=url;anchor.download="videl-post.json";anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);setResult({ok:true,message:"Text and buttons exported. Download attached local images separately."})}catch(error){setResult({ok:false,message:(error as Error).message})}
          }}>Export post JSON</button>
          <label className="ios-btn ios-btn-glass cursor-pointer text-sm">Import post JSON<input aria-label="Import post JSON" type="file" accept=".json" className="sr-only" disabled={busy} onChange={async event=>{
            const file=event.target.files?.[0];event.target.value="";if(!file)return;
            try{if(file.size>131072)throw new Error("Post JSON must be smaller than 128 KB.");const draft=importDraftDocument(JSON.parse(await file.text()));if(!isOwner)draft.chatId="";restoreDraft(draft)}catch(error){setResult({ok:false,message:(error as Error).message})}
          }}/></label>
          <button
            disabled={busy}
            onClick={saveDraft}
            className="ios-btn ios-btn-glass text-sm"
          >
            <Clipboard size={15} aria-hidden /> Save draft
          </button>
        </div>
      </header>
      <PostFlow
        characters={visibleLength(text)}
        limit={limit}
        hasImage={hasImage}
        buttons={buttons.reduce((total, row) => total + row.length, 0)}
        canPublish={Boolean(text.trim() || mediaUrl || localImage)}
        words={plainPostText(text).trim().split(/\s+/).filter(Boolean).length}
        save={{
          state: saveState,
          note:
            saveState === "error"
              ? "autosave unavailable"
              : saveState === "saved" && savedAt
                ? `saved ${Math.max(0, Math.round((Date.now() - savedAt) / 1000))}s ago`
                : isOwner
                  ? "⌘S draft · ⌘⏎ publish"
                  : "autosave on this device",
        }}
        schedule={{ ready: isOwner, note: isOwner ? "⌘S draft · ⌘⏎ publish" : "sign in to schedule" }}
      />

      {undo.length ? (
        <section role="status" className="post-undo">
          <span>
            {undo[undo.length - 1].reason}. The previous post is still here
            {undo.length > 1 ? ` (${undo.length} steps back)` : ""}.
          </span>
          <button type="button" className="ios-btn ios-btn-glass text-xs" onClick={undoLast}>
            Undo
          </button>
          <button
            type="button"
            className="post-undo-dismiss"
            onClick={() => setUndo([])}
            aria-label="Dismiss"
          >
            ×
          </button>
        </section>
      ) : null}

      {recovery && (
        <section
          role="status"
          className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-[#b5c4a5]/25 bg-[#b5c4a5]/5 p-4 text-xs"
        >
          <div className="min-w-0 flex-1">
            <p className="font-semibold">Unfinished post found</p>
            <p className="mt-1 text-stone-400">
              {new Date(recovery.savedAt).toLocaleString()} · Text and links
              only; reattach any local image.
            </p>
          </div>
          <button
            disabled={busy}
            onClick={() => restoreDraft(recovery)}
            className="ios-btn ios-btn-glass text-xs"
          >
            Restore
          </button>
          <button
            onClick={() => {
              setRecovery(null);
              try {
                localStorage.removeItem(RECOVERY_KEY);
              } catch {}
            }}
            className="text-stone-400 underline"
          >
            Discard recovery
          </button>
        </section>
      )}
      {autoStatus && (
        <p role="status" className="mt-3 text-[10px] text-stone-400">
          {autoStatus}
        </p>
      )}
      <div className="mt-5 flex flex-wrap gap-2" role="group" aria-label="Post workspace mode">
        <button
          aria-pressed={!showTemplates && !showAssets && !showCovers}
          onClick={() => {
            setShowTemplates(false);
            setShowAssets(false);
            setShowCovers(false);
          }}
          className={`ios-btn text-xs ${!showTemplates && !showAssets && !showCovers ? "ios-btn-primary" : "ios-btn-glass"}`}
        >
          Create Post
        </button>
        <button
          aria-pressed={showTemplates}
          onClick={() => {
            setShowTemplates(true);
            setShowAssets(false);
            setShowCovers(false);
          }}
          className={`ios-btn text-xs ${showTemplates ? "ios-btn-primary" : "ios-btn-glass"}`}
        >
          Text Templates
        </button>
        <button
          aria-pressed={showCovers}
          onClick={() => {
            setShowCovers(true);
            setShowTemplates(false);
            setShowAssets(false);
          }}
          className={`ios-btn text-xs ${showCovers ? "ios-btn-primary" : "ios-btn-glass"}`}
        >
          Cover Library ✨
        </button>
        <button
          aria-pressed={showAssets}
          onClick={() => {
            setShowAssets(true);
            setShowTemplates(false);
            setShowCovers(false);
          }}
          className={`ios-btn text-xs ${showAssets ? "ios-btn-primary" : "ios-btn-glass"}`}
        >
          Design Image
        </button>
      </div>
      {!showTemplates && !showAssets && !showCovers && (
        <section className="post-editorial-banner mt-5 flex items-center justify-between gap-5 overflow-hidden rounded-2xl border border-white/10 p-5 sm:p-7">
          <img className="post-editorial-art" src="/studio/flow.jpg" alt="" aria-hidden decoding="async" />
          <div className="max-w-md">
            <p className="post-eyebrow">THE PUBLISHING DESK</p>
            <h2 className="post-serif mt-3 text-3xl leading-tight">
              Make every post
              <br />
              worth pausing for.
            </h2>
            <p className="mt-3 max-w-xs text-xs leading-6 text-stone-400">
              Write your post, design a custom image, then preview everything
              before publishing.
            </p>
            <button
              onClick={() => setShowAssets(true)}
              className="mt-4 inline-flex min-h-9 items-center text-xs text-[#cbd8ba] underline underline-offset-4"
            >
              Open the image composer
            </button>
          </div>
          <img
            src="/post-assets/weekly.png"
            alt="The weekly edit — an example from the cover collection"
            width={1200}
            height={675}
            className="hidden w-[40%] -rotate-3 rounded-xl border border-white/10 shadow-xl sm:block"
          />
        </section>
      )}
      <div hidden={!showAssets}>
        <ImageComposer
          disabled={busy}
          onAttach={(file) => {
            setLocalImage(file);
            setShowAssets(false);
            setResult({
              ok: true,
              message:
                "Custom design attached. Review the preview and caption before publishing. Download the image to keep a copy.",
            });
          }}
        />
      </div>
      {showCovers && (
        <PostAssetLibrary
          selected={mediaUrl}
          disabled={busy}
          onSelect={async (path) => {
            try {
              setResult(null);
              const response = await fetch(path);
              if (!response.ok) throw new Error("Could not open this cover.");
              const blob = await response.blob();
              if (blob.size > 4 * 1024 * 1024)
                throw new Error("This cover is larger than 4 MB.");
              const name = path.startsWith("data:")
                ? "your-cover.png"
                : path.split("/").pop() || "cover.png";
              setMediaUrl("");
              setLocalImage(new File([blob], name, { type: blob.type || "image/png" }));
              setShowCovers(false);
              setResult({
                ok: true,
                message:
                  "Cover attached to your post. Add a caption, review the preview, then publish.",
              });
            } catch (error) {
              setResult({
                ok: false,
                message:
                  error instanceof Error
                    ? error.message
                    : "That cover could not be attached.",
              });
            }
          }}
        />
      )}
      {showTemplates && (
        <section className="mt-4 grid gap-3 sm:grid-cols-3">
          {templates.map((template) => (
            <button
              key={template.title}
              disabled={busy}
              onClick={() => {
                if (
                  text.trim() &&
                  !window.confirm(
                    "Replace the current post text with this template? Save a draft first if you want to keep it.",
                  )
                )
                  return;
                setText(template.text);
                setParseMode("HTML");
                setShowTemplates(false);
              }}
              className="ios-card ios-card-interactive p-5"
            >
              <span className="ios-pill ios-pill-blue">{template.tag}</span>
              <h2 className="mt-4 text-sm font-semibold">{template.title}</h2>
              <p className="mt-2 text-xs leading-5 text-stone-400">
                An editable starting point. Customize every detail before
                sending.
              </p>
              <span className="mt-4 block text-xs text-[#c5d6b3]">
                Use template ↗
              </span>
            </button>
          ))}
        </section>
      )}
      <fieldset
        disabled={busy}
        className="mt-6 grid min-w-0 gap-4 lg:grid-cols-[1.15fr_0.85fr]"
      >
        <section id="post-write" tabIndex={-1} className="space-y-4">
          {isOwner && (
            <div className="ios-card p-4 sm:p-5">
              <div className="flex flex-wrap items-end gap-3">
                <label className="min-w-[220px] flex-1 text-sm font-medium">
                  Channel or chat ID
                  <input
                    value={chatId}
                    onChange={(e) => setChatId(e.target.value)}
                    placeholder="@channelname or -100…"
                    className="ios-input mt-2"
                    autoComplete="off"
                  />
                </label>
                <div className="rounded-xl border border-white/10 px-3 py-3 text-xs text-stone-400">
                  Visual formatting
                  <span className="mt-1 block text-[10px] text-stone-500">
                    Telegram-ready automatically
                  </span>
                </div>
              </div>
              <p className="mt-3 ios-caption">
                The bot must be a member with permission to post. Private
                destinations generally require their numeric chat ID.
              </p>
            </div>
          )}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <h2 className="ios-caption2">Post text</h2>
              <span
                className={`text-[10px] ${remaining < 0 ? "text-amber-300" : "text-stone-500"}`}
              >
                {visibleLength(text).toLocaleString()} /{" "}
                {hasImage ? "1,024 caption" : "4,096 text"}
              </span>
            </div>
            <RichEditor
              disabled={busy}
              value={text}
              onChange={setText}
              limit={limit}
              placeholder="Write a Telegram announcement…"
            />
          </div>
          <div className="ios-card space-y-3 p-4 sm:p-5">
            <div>
              <h2 className="ios-caption2">Post image</h2>
              <p className="mt-1 ios-caption">
                Design your own image, upload a photo inside the composer, or
                use a public HTTPS image URL.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => {
                  setShowAssets(true);
                  setShowTemplates(false);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
                className="ios-btn ios-btn-glass text-xs"
              >
                Design custom image
              </button>
              <button
                onClick={() => {
                  setShowCovers(true);
                  setShowAssets(false);
                  setShowTemplates(false);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
                className="ios-btn ios-btn-glass text-xs"
              >
                Browse cover library
              </button>
              {mediaUrl && (
                <button
                  onClick={() => {
                    setLocalImage(null);
                    setMediaUrl("");
                  }}
                  className="ios-btn ios-btn-glass text-xs"
                >
                  Remove image
                </button>
              )}
            </div>
            <input
              value={localImage ? "" : mediaUrl}
              onChange={(e) => {
                setLocalImage(null);
                setMediaUrl(e.target.value);
              }}
              placeholder={
                localImage
                  ? "Custom image attached — paste a URL to replace it"
                  : "https://example.com/image.jpg"
              }
              className="ios-input"
            />
            {mediaUrl && (
              <img
                key={mediaUrl}
                src={mediaUrl}
                alt="Post media preview"
                className="max-h-60 w-full rounded-xl border border-white/10 object-contain"
                onError={(e) => {
                  (e.currentTarget as HTMLImageElement).style.display = "none";
                }}
              />
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="ios-btn ios-btn-glass text-sm"
              disabled={!text.trim()}
              onClick={() => {
                const blob = new Blob([plainPostText(text)], {
                  type: "text/plain;charset=utf-8",
                });
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement("a");
                anchor.href = url;
                anchor.download = "videl-post.txt";
                anchor.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
              }}
            >
              Download text
            </button>
            <button
              className="ios-btn ios-btn-glass text-sm"
              disabled={!text.trim()}
              onClick={async () => {
                try {
                  const canShare = typeof navigator.share === "function";
                  if (canShare)
                    await navigator.share({ text: plainPostText(text) });
                  else await navigator.clipboard.writeText(plainPostText(text));
                  setResult({
                    ok: true,
                    message: canShare
                      ? "Share sheet opened."
                      : "Post text copied.",
                  });
                } catch (error) {
                  if ((error as Error).name !== "AbortError")
                    setResult({
                      ok: false,
                      message:
                        "Sharing unavailable. Use Download text instead.",
                    });
                }
              }}
            >
              Share post
            </button>
          </div>
          <div id="post-design" tabIndex={-1} className="scroll-mt-24">
            <ButtonBuilder value={buttons} onChange={setButtons} />
          </div>
          {result && (
            <div
              role={result.ok ? "status" : "alert"}
              className={`rounded-xl border p-3 text-sm ${result.ok ? "border-emerald-300/20 bg-emerald-300/5 text-emerald-100" : "border-amber-300/20 bg-amber-300/5 text-amber-100"}`}
            >
              {result.message}
            </div>
          )}
          {remaining < 0 && (
            <p role="alert" className="text-xs text-amber-200">
              Remove {Math.abs(remaining).toLocaleString()} characters before
              publishing
              {hasImage
                ? ", or remove the image to use a longer text post"
                : ""}
              .
            </p>
          )}
          {isOwner && (
            <>
              <label className="flex items-start gap-3 rounded-xl border border-[#b5c4a5]/15 bg-[#b5c4a5]/5 p-4 text-xs leading-5 text-stone-400">
                <input
                  type="checkbox"
                  checked={reviewed}
                  disabled={busy}
                  onChange={(e) => setReviewed(e.target.checked)}
                  className="mt-1"
                />
                I reviewed the destination and preview. Publish this post to{" "}
                {chatId.trim() || "the selected destination"}.
              </label>
              <button
                onClick={() => void sendPost()}
                disabled={
                  busy ||
                  remaining < 0 ||
                  !reviewed ||
                  !chatId.trim() ||
                  (!text.trim() && !hasImage)
                }
                className="ios-btn ios-btn-primary w-full disabled:opacity-50"
              >
                {busy ? "Sending to Telegram…" : "Publish post"}
                <Send size={16} aria-hidden />
              </button>
            </>
          )}
        </section>
        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <section id="post-preview" tabIndex={-1} className="ios-card-elevated scroll-mt-24 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold">Preview</h2>
                <p className="ios-caption">
                  Formatting preview, not a sent message
                </p>
              </div>
              <button
                onClick={() => setLightPreview((v) => !v)}
                aria-label="Toggle preview theme"
                className="ios-btn ios-btn-glass text-xs"
              >
                <Eye size={14} />
                {lightPreview ? "Light" : "Dark"}
              </button>
            </div>
            <div className="mt-4">
              <ChannelPreview
                channel={isOwner ? chatId : "Your post"}
                text={text}
                mediaUrl={mediaUrl}
                buttons={buttons}
                theme={previewTheme}
              />
            </div>
            <div className="mt-3 flex gap-2">
              <button
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(plainPostText(text));
                    setResult({ ok: true, message: "Post text copied." });
                  } catch {
                    setResult({
                      ok: false,
                      message:
                        "Clipboard access was blocked. Select and copy the post text manually.",
                    });
                  }
                }}
                className="ios-btn ios-btn-glass flex-1 text-xs"
              >
                <Clipboard size={14} /> Copy text
              </button>
              <a
                href="https://t.me/Videl0Bot"
                target="_blank"
                rel="noreferrer"
                className="ios-btn ios-btn-glass text-xs"
              >
                Open bot <ArrowUpRight size={14} />
              </a>
            </div>
          </section>
          <div id="post-queue" tabIndex={-1} className="scroll-mt-24" />
          {isOwner&&<ScheduledPosts chatId={chatId} text={text} mediaUrl={mediaUrl} buttons={buttons} hasLocalImage={!!localImage} reviewed={reviewed} disabled={busy||remaining<0}/>}
          <section className="ios-card space-y-3 p-4"><h2 className="font-semibold">Publishing checklist</h2><p className="ios-caption">Advisory checks, not a guarantee of delivery.</p>{postChecks(text,!!mediaUrl||!!localImage,buttons).map(check=><div key={check.label} className="rounded-xl bg-white/[0.035] p-3"><div className="text-sm">{check.state==="pass"?"✓":check.state==="error"?"Fix":"Review"} · {check.label}</div><p className="ios-caption mt-1">{check.detail}</p></div>)}</section>
          <section className="ios-card space-y-3 p-4"><h2 className="font-semibold">Version history</h2><p className="ios-caption">Up to 20 manual checkpoints in this browser. Image files are excluded.</p><button className="ios-btn ios-btn-glass text-xs" disabled={busy} onClick={saveVersion}>Save version</button>{versions.map((version,i)=><div className="rounded-xl bg-white/[0.035] p-3" key={version.id}><p className="text-xs">{new Date(version.savedAt).toLocaleString()} · {visibleLength(version.text)} characters</p><p className="ios-caption truncate">{plainPostText(version.text).slice(0,100)||"Image/button post"}</p><button className="ios-pill mt-2" disabled={busy} onClick={()=>restoreDraft({...version,chatId:isOwner?version.chatId:""})}>Restore version {versions.length-i}</button></div>)}</section>
          <section className="ios-card p-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold">Local drafts</h2>
                <p className="mt-1 ios-caption">
                  Stored in this browser only · not synced
                </p>
              </div>
              <span className="ios-pill">{drafts.length}</span>
            </div>
            <div className="mt-3 space-y-2">
              {drafts.length ? (
                drafts.map((draft) => (
                  <div
                    key={draft.id}
                    className="flex items-center gap-2 rounded-xl bg-white/[0.035] p-3"
                  >
                    <button
                      onClick={() => restoreDraft(draft)}
                      className="min-w-0 flex-1 text-left"
                    >
                      <span className="block truncate text-sm font-medium">
                        {draft.text.replace(/<[^>]*>/g, " ").trim() ||
                          draft.mediaUrl ||
                          "Untitled post"}
                      </span>
                      <span className="mt-1 block text-xs text-[var(--ios-label-secondary)]">
                        {draft.chatId || "No destination"} ·{" "}
                        {new Date(draft.savedAt).toLocaleString()}
                      </span>
                    </button>
                    <button
                      aria-label="Make a copy of this draft"
                      title="Make a copy"
                      onClick={() => copySavedDraft(draft)}
                      className="rounded-lg p-2 text-white/55 hover:bg-white/10 hover:text-white"
                    >
                      <Copy size={15} />
                    </button>
                    <button
                      aria-label="Delete draft"
                      onClick={() =>
                        persistDrafts(drafts.filter((x) => x.id !== draft.id))
                      }
                      className="rounded-lg p-2 text-white/55 hover:bg-white/10 hover:text-white"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))
              ) : (
                <p className="rounded-xl bg-white/[0.03] p-3 text-sm text-[var(--ios-label-secondary)]">
                  No local drafts saved.
                </p>
              )}
            </div>
          </section>
        </aside>
      </fieldset>
    </main>
  );
}
