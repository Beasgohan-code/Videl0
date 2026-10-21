"use client";
import { useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Strikethrough,
  EyeOff,
  Code,
  Quote,
  Link2,
  Smile,
  X,
  Check,
  Sparkles,
} from "lucide-react";
import { editorHtml, safeLink, telegramHtml } from "@/lib/telegram-format";
import { insertPremiumEmoji, richExtensions } from "./rich-extensions";
import { PremiumEmojiPicker } from "./PremiumEmojiPicker";

const bubbleOptions = { placement: "top" as const };

/**
 * Telegram-style message composer: WYSIWYG formatting by selection, premium
 * emoji, links and spoilers — no HTML tags ever shown to the writer.
 */
export function RichComposer({
  value,
  onChange,
  placeholder = "Message…",
  disabled = false,
  onSubmit,
  limit = 4096,
  label = "Message as bot",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  onSubmit?: () => void;
  limit?: number;
  label?: string;
}) {
  const callback = useRef(onChange);
  callback.current = onChange;
  const submit = useRef(onSubmit);
  submit.current = onSubmit;
  const emitted = useRef(value);
  const [focus, setFocus] = useState(false);
  const [panel, setPanel] = useState<"emoji" | null>(null);
  const [linkOpen, setLinkOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  const editor = useEditor({
    immediatelyRender: false,
    shouldRerenderOnTransaction: true,
    extensions: richExtensions(placeholder),
    content: editorHtml(value),
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    editorProps: {
      attributes: {
        class: "tg-rich-input",
        role: "textbox",
        "aria-label": label,
        "aria-multiline": "true",
      },
      handleKeyDown: (_view, event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && submit.current) {
          event.preventDefault();
          submit.current();
          return true;
        }
        return false;
      },
    },
    onUpdate: ({ editor }) => {
      const html = telegramHtml(editor.getJSON());
      emitted.current = html;
      callback.current(html);
    },
  });

  useEffect(() => {
    if (editor && value !== emitted.current) {
      editor.commands.setContent(editorHtml(value), { emitUpdate: false });
      emitted.current = value;
    }
  }, [editor, value]);
  useEffect(() => {
    editor?.setEditable(!disabled, false);
  }, [editor, disabled]);

  function applyLink() {
    if (!editor) return;
    if (!url.trim()) {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      setLinkOpen(false);
      return;
    }
    const href = safeLink(url.trim());
    if (!href) {
      setError("Enter a complete https://, http:// or tg:// link.");
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href }).run();
    setError("");
    setLinkOpen(false);
    setUrl("");
  }

  const tools = [
    { label: "Bold", icon: Bold, active: editor?.isActive("bold"), run: () => editor?.chain().focus().toggleBold().run() },
    { label: "Italic", icon: Italic, active: editor?.isActive("italic"), run: () => editor?.chain().focus().toggleItalic().run() },
    { label: "Underline", icon: UnderlineIcon, active: editor?.isActive("underline"), run: () => editor?.chain().focus().toggleUnderline().run() },
    { label: "Strikethrough", icon: Strikethrough, active: editor?.isActive("strike"), run: () => editor?.chain().focus().toggleStrike().run() },
    { label: "Spoiler", icon: EyeOff, active: editor?.isActive("spoiler"), run: () => editor?.chain().focus().toggleMark("spoiler").run() },
    { label: "Monospace", icon: Code, active: editor?.isActive("code"), run: () => editor?.chain().focus().toggleCode().run() },
    { label: "Quote", icon: Quote, active: editor?.isActive("blockquote"), run: () => editor?.chain().focus().toggleBlockquote().run() },
    { label: "Link", icon: Link2, active: editor?.isActive("link"), run: () => setLinkOpen((open) => !open) },
  ];

  return (
    <div className={`tg-rich-composer ${focus ? "tg-rich-focused" : ""}`}>
      <div className="tg-rich-toolbar" role="toolbar" aria-label="Format message">
        {tools.map((tool) => (
          <button
            key={tool.label}
            type="button"
            aria-label={tool.label}
            aria-pressed={!!tool.active}
            title={tool.label}
            disabled={disabled || !editor}
            onPointerDown={(event) => event.preventDefault()}
            onClick={tool.run}
            className={`tg-rich-tool ${tool.active ? "tg-rich-tool-active" : ""}`}
          >
            <tool.icon size={14} />
          </button>
        ))}
        <button
          type="button"
          aria-label="Premium emoji"
          aria-pressed={panel === "emoji"}
          title="Premium emoji"
          disabled={disabled || !editor}
          onPointerDown={(event) => event.preventDefault()}
          onClick={() => setPanel(panel === "emoji" ? null : "emoji")}
          className={`tg-rich-tool ${panel === "emoji" ? "tg-rich-tool-active" : ""}`}
        >
          <Smile size={14} />
        </button>
        <span className="ml-auto hidden items-center gap-1 text-[9px] text-white/25 sm:flex">
          <Sparkles size={10} /> Premium emoji & formatting
        </span>
      </div>

      {panel === "emoji" && editor && (
        <div className="tg-emoji-pop">
          <PremiumEmojiPicker
            compact
            onInsert={(id, char) => {
              insertPremiumEmoji(editor, id, char);
              setPanel(null);
            }}
            onClose={() => setPanel(null)}
          />
        </div>
      )}

      {linkOpen && (
        <div className="flex flex-wrap items-center gap-2 border-b border-white/10 px-3 py-2">
          <input
            autoFocus
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                applyLink();
              }
              if (event.key === "Escape") setLinkOpen(false);
            }}
            placeholder="https://example.com"
            aria-label="Link address"
            className="min-w-0 flex-1 rounded-lg bg-black/30 px-2.5 py-1.5 text-xs text-white/90 outline-none ring-1 ring-white/10 placeholder:text-white/25"
          />
          <button type="button" onClick={applyLink} aria-label="Apply link" className="rounded-lg bg-sky-500/80 p-1.5 text-white hover:bg-sky-400">
            <Check size={14} />
          </button>
          <button type="button" onClick={() => setLinkOpen(false)} aria-label="Cancel link" className="rounded-lg p-1.5 text-white/50 hover:bg-white/10">
            <X size={14} />
          </button>
          {error && (
            <p role="alert" className="w-full text-[10px] text-amber-200">
              {error}
            </p>
          )}
        </div>
      )}

      {editor && (
        <BubbleMenu editor={editor} options={bubbleOptions}>
          <div className="rich-bubble" role="toolbar" aria-label="Format selected text">
            {tools.slice(0, 8).map((tool) => (
              <button
                key={tool.label}
                type="button"
                aria-label={`Selection ${tool.label}`}
                aria-pressed={!!tool.active}
                title={tool.label}
                onPointerDown={(event) => event.preventDefault()}
                onClick={tool.run}
                className={`rich-bubble-tool ${tool.active ? "rich-bubble-tool-active" : ""}`}
              >
                <tool.icon size={16} />
              </button>
            ))}
          </div>
        </BubbleMenu>
      )}

      <EditorContent editor={editor} />

      <p className="tg-rich-hint">
        Select text to style it · Ctrl+Enter sends · {limit.toLocaleString()} max
      </p>
    </div>
  );
}
