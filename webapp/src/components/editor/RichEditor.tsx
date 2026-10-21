"use client";
import { useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Strikethrough,
  Link2,
  Quote,
  Code,
  Code2,
  EyeOff,
  List,
  ListOrdered,
  Undo2,
  Redo2,
  RemoveFormatting,
  Smile,
  Eye,
  CodeXml,
  Copy,
  Check,
  CornerDownLeft,
  Sparkles,
} from "lucide-react";
import { editorHtml, previewHtml, safeLink, telegramHtml, visibleLength } from "@/lib/telegram-format";
import { insertPremiumEmoji, richExtensions } from "./rich-extensions";
import { PremiumEmojiPicker } from "./PremiumEmojiPicker";

// BubbleMenu dispatches a transaction when options change. Keep this stable to
// avoid a render/transaction loop with React 19 and Tiptap rerendering enabled.
const bubbleOptions = { placement: "top" as const };

type Panel = null | "emoji" | "preview" | "html";

export function RichEditor({
  value,
  onChange,
  placeholder,
  disabled = false,
  limit = 4096,
  onSubmit,
  label = "Post text — visual rich editor",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
  limit?: number;
  onSubmit?: () => void;
  label?: string;
}) {
  const callback = useRef(onChange);
  callback.current = onChange;
  const submit = useRef(onSubmit);
  submit.current = onSubmit;
  const emitted = useRef(value);
  const [linkOpen, setLinkOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [panel, setPanel] = useState<Panel>(null);
  const [copied, setCopied] = useState(false);

  const editor = useEditor({
    immediatelyRender: false,
    shouldRerenderOnTransaction: true,
    extensions: richExtensions(placeholder || "Write your post. Select any words to style them."),
    content: editorHtml(value),
    editorProps: {
      attributes: {
        class: "visual-post-editor",
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
  useEffect(() => {
    if (!panel) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPanel(null);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [panel]);

  function openLink() {
    if (!editor) return;
    setUrl(editor.getAttributes("link").href || "");
    setError("");
    setLinkOpen((open) => !open);
  }
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
    setLinkOpen(false);
  }

  const inline = [
    { label: "Bold", shortcut: "Ctrl B", icon: Bold, active: editor?.isActive("bold"), run: () => editor?.chain().focus().toggleBold().run() },
    { label: "Italic", shortcut: "Ctrl I", icon: Italic, active: editor?.isActive("italic"), run: () => editor?.chain().focus().toggleItalic().run() },
    { label: "Underline", shortcut: "Ctrl U", icon: UnderlineIcon, active: editor?.isActive("underline"), run: () => editor?.chain().focus().toggleUnderline().run() },
    { label: "Strikethrough", shortcut: "Ctrl Shift S", icon: Strikethrough, active: editor?.isActive("strike"), run: () => editor?.chain().focus().toggleStrike().run() },
    { label: "Spoiler", shortcut: "Ctrl Shift P", icon: EyeOff, active: editor?.isActive("spoiler"), run: () => editor?.chain().focus().toggleMark("spoiler").run() },
    { label: "Link", shortcut: "Ctrl K", icon: Link2, active: editor?.isActive("link"), run: openLink },
  ];
  const blocks = [
    { label: "Monospace", icon: Code, active: editor?.isActive("code"), run: () => editor?.chain().focus().toggleCode().run() },
    { label: "Code block", icon: Code2, active: editor?.isActive("codeBlock"), run: () => editor?.chain().focus().toggleCodeBlock().run() },
    { label: "Quote", icon: Quote, active: editor?.isActive("blockquote"), run: () => editor?.chain().focus().toggleBlockquote().run() },
    { label: "Bullet list", icon: List, active: editor?.isActive("bulletList"), run: () => editor?.chain().focus().toggleBulletList().run() },
    { label: "Numbered list", icon: ListOrdered, active: editor?.isActive("orderedList"), run: () => editor?.chain().focus().toggleOrderedList().run() },
  ];
  const length = visibleLength(value);
  const over = length > limit;

  return (
    <div className="ios-card overflow-hidden">
      <div className="rich-toolbar" role="toolbar" aria-label="Text formatting">
        <div className="rich-toolbar-group">
          {inline.map((tool) => (
            <button
              type="button"
              key={tool.label}
              aria-label={tool.label}
              aria-pressed={!!tool.active}
              title={`${tool.label} · ${tool.shortcut}`}
              disabled={disabled || !editor}
              onPointerDown={(event) => event.preventDefault()}
              onClick={tool.run}
              className={`rich-tool ${tool.active ? "rich-tool-active" : ""}`}
            >
              <tool.icon size={15} />
            </button>
          ))}
        </div>
        <span className="rich-toolbar-divider" />
        <div className="rich-toolbar-group">
          {blocks.map((tool) => (
            <button
              type="button"
              key={tool.label}
              aria-label={tool.label}
              aria-pressed={!!tool.active}
              title={tool.label}
              disabled={disabled || !editor}
              onPointerDown={(event) => event.preventDefault()}
              onClick={tool.run}
              className={`rich-tool ${tool.active ? "rich-tool-active" : ""}`}
            >
              <tool.icon size={15} />
            </button>
          ))}
        </div>
        <span className="rich-toolbar-divider" />
        <button
          type="button"
          aria-label="Insert premium emoji"
          aria-pressed={panel === "emoji"}
          title="Premium emoji"
          disabled={disabled || !editor}
          onPointerDown={(event) => event.preventDefault()}
          onClick={() => setPanel(panel === "emoji" ? null : "emoji")}
          className={`rich-tool ${panel === "emoji" ? "rich-tool-active" : ""}`}
        >
          <Smile size={15} />
        </button>
        <button
          type="button"
          aria-label="Toggle Telegram preview"
          aria-pressed={panel === "preview"}
          title="Telegram preview"
          onPointerDown={(event) => event.preventDefault()}
          onClick={() => setPanel(panel === "preview" ? null : "preview")}
          className={`rich-tool ${panel === "preview" ? "rich-tool-active" : ""}`}
        >
          <Eye size={15} />
        </button>
        <button
          type="button"
          aria-label="Show Telegram HTML"
          aria-pressed={panel === "html"}
          title="Telegram HTML"
          onPointerDown={(event) => event.preventDefault()}
          onClick={() => setPanel(panel === "html" ? null : "html")}
          className={`rich-tool ${panel === "html" ? "rich-tool-active" : ""}`}
        >
          <CodeXml size={15} />
        </button>
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            aria-label="Clear formatting"
            title="Clear formatting"
            disabled={disabled || !editor}
            onPointerDown={(event) => event.preventDefault()}
            onClick={() => editor?.chain().focus().unsetAllMarks().clearNodes().run()}
            className="rich-tool"
          >
            <RemoveFormatting size={15} />
          </button>
          <button
            type="button"
            aria-label="Undo"
            title="Undo"
            disabled={disabled || !editor?.can().undo()}
            onPointerDown={(event) => event.preventDefault()}
            onClick={() => editor?.chain().focus().undo().run()}
            className="rich-tool disabled:opacity-25"
          >
            <Undo2 size={15} />
          </button>
          <button
            type="button"
            aria-label="Redo"
            title="Redo"
            disabled={disabled || !editor?.can().redo()}
            onPointerDown={(event) => event.preventDefault()}
            onClick={() => editor?.chain().focus().redo().run()}
            className="rich-tool disabled:opacity-25"
          >
            <Redo2 size={15} />
          </button>
        </div>
      </div>

      {panel === "emoji" && editor && (
        <div className="border-b border-white/10 p-3">
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

      {panel === "preview" && (
        <div className="border-b border-white/10 bg-[#0e1621] p-4">
          <p className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[.16em] text-white/40">
            <Sparkles size={11} /> Telegram preview
          </p>
          {value.trim() ? (
            <div className="telegram-rich max-w-[92%] rounded-2xl rounded-tl-md bg-[#182533] px-3.5 py-3 text-[13px] leading-6 text-indigo-50/90" dangerouslySetInnerHTML={{ __html: previewHtml(value) }} />
          ) : (
            <p className="text-xs italic text-white/35">Start typing to see the Telegram bubble.</p>
          )}
          <p className="mt-2 text-[10px] text-white/25">Rendered from the exact HTML the bot sends.</p>
        </div>
      )}

      {panel === "html" && (
        <div className="border-b border-white/10 p-4">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[10px] font-bold uppercase tracking-[.16em] text-white/40">Telegram HTML</p>
            <button
              type="button"
              onClick={() => {
                void navigator.clipboard.writeText(value).then(() => {
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                });
              }}
              className="flex items-center gap-1 text-[10px] text-[#c5d6b3] hover:underline"
            >
              {copied ? <Check size={11} /> : <Copy size={11} />} {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-black/35 p-3 text-[11px] leading-5 text-[#c9d8c0]">{value || "(empty)"}</pre>
          <p className="mt-2 text-[10px] text-white/25">Valid Telegram nesting is guaranteed by the composer. The bot re-checks it before sending.</p>
        </div>
      )}

      {linkOpen && (
        <div className="border-b border-white/10 p-3" role="group" aria-label="Edit selected text link">
          <label htmlFor="post-link" className="text-xs text-stone-400">
            Link address · leave empty to remove
          </label>
          <div className="mt-2 flex flex-wrap gap-2">
            <input
              id="post-link"
              autoFocus
              type="url"
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
              className="ios-input flex-1"
            />
            <button type="button" onClick={applyLink} className="ios-btn ios-btn-primary text-xs">
              Apply link
            </button>
            <button type="button" onClick={() => setLinkOpen(false)} className="ios-btn ios-btn-glass text-xs">
              Cancel
            </button>
          </div>
          {error && (
            <p role="alert" className="mt-2 text-xs text-amber-200">
              {error}
            </p>
          )}
        </div>
      )}

      {editor && (
        <BubbleMenu editor={editor} options={bubbleOptions}>
          <div className="rich-bubble" role="toolbar" aria-label="Format selected text">
            {[...inline, ...blocks.slice(0, 3)].map((tool) => (
              <button
                type="button"
                key={tool.label}
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

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/5 px-4 py-3 text-[10px] text-stone-500">
        <span className="flex items-center gap-1.5">
          <CornerDownLeft size={11} /> Select text to format · markdown shortcuts work · Ctrl+Enter previews and sends
        </span>
        <span className={`font-mono ${over ? "font-bold text-rose-300" : ""}`}>
          {length.toLocaleString()}/{limit.toLocaleString()}
          {over ? " · too long" : ""}
        </span>
      </div>
    </div>
  );
}
