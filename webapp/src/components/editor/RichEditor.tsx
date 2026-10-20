"use client";
import { useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import { Mark, mergeAttributes } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Strikethrough,
  Link2,
  Quote,
  Code,
  EyeOff,
  List,
  ListOrdered,
  Undo2,
  Redo2,
  RemoveFormatting,
} from "lucide-react";
import {
  editorHtml,
  safeLink,
  telegramHtml,
  visibleLength,
} from "@/lib/telegram-format";
// BubbleMenu dispatches a transaction when options change. Keep this stable to
// avoid a render/transaction loop with React 19 and Tiptap rerendering enabled.
const bubbleOptions = { placement: "top" as const };
const Spoiler = Mark.create({
  name: "spoiler",
  parseHTML: () => [
    { tag: 'span[data-spoiler="true"]' },
    { tag: "tg-spoiler" },
  ],
  renderHTML: ({ HTMLAttributes }) => [
    "span",
    mergeAttributes(HTMLAttributes, { "data-spoiler": "true" }),
    0,
  ],
});
export function RichEditor({
  value,
  onChange,
  placeholder,
  disabled = false,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  const callback = useRef(onChange);
  callback.current = onChange;
  const emitted = useRef(value);
  const [linkOpen, setLinkOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const editor = useEditor({
    immediatelyRender: false,
    shouldRerenderOnTransaction: true,
    extensions: [
      StarterKit.configure({
        heading: { levels: [2] },
        horizontalRule: false,
        link: false,
        underline: false,
      }),
      Underline,
      Link.configure({
        openOnClick: false,
        autolink: true,
        linkOnPaste: true,
        protocols: ["https", "http", "tg"],
        validate: (url) => Boolean(safeLink(url)),
      }),
      Spoiler,
      Placeholder.configure({
        placeholder:
          placeholder || "Write your post. Select any words to style them.",
      }),
    ],
    content: editorHtml(value),
    editorProps: {
      attributes: {
        class: "visual-post-editor",
        role: "textbox",
        "aria-label": "Post text — visual rich editor",
        "aria-multiline": "true",
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
  function openLink() {
    if (!editor) return;
    setUrl(editor.getAttributes("link").href || "");
    setError("");
    setLinkOpen(true);
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
  const basic = [
    {
      label: "Bold",
      icon: Bold,
      active: editor?.isActive("bold"),
      run: () => editor?.chain().focus().toggleBold().run(),
    },
    {
      label: "Italic",
      icon: Italic,
      active: editor?.isActive("italic"),
      run: () => editor?.chain().focus().toggleItalic().run(),
    },
    {
      label: "Underline",
      icon: UnderlineIcon,
      active: editor?.isActive("underline"),
      run: () => editor?.chain().focus().toggleUnderline().run(),
    },
    {
      label: "Strikethrough",
      icon: Strikethrough,
      active: editor?.isActive("strike"),
      run: () => editor?.chain().focus().toggleStrike().run(),
    },
    {
      label: "Link",
      icon: Link2,
      active: editor?.isActive("link"),
      run: openLink,
    },
  ];
  const tools = [
    ...basic,
    {
      label: "Spoiler",
      icon: EyeOff,
      active: editor?.isActive("spoiler"),
      run: () => editor?.chain().focus().toggleMark("spoiler").run(),
    },
    {
      label: "Quote",
      icon: Quote,
      active: editor?.isActive("blockquote"),
      run: () => editor?.chain().focus().toggleBlockquote().run(),
    },
    {
      label: "Code",
      icon: Code,
      active: editor?.isActive("code"),
      run: () => editor?.chain().focus().toggleCode().run(),
    },
    {
      label: "Bullet list",
      icon: List,
      active: editor?.isActive("bulletList"),
      run: () => editor?.chain().focus().toggleBulletList().run(),
    },
    {
      label: "Numbered list",
      icon: ListOrdered,
      active: editor?.isActive("orderedList"),
      run: () => editor?.chain().focus().toggleOrderedList().run(),
    },
    {
      label: "Clear formatting",
      icon: RemoveFormatting,
      active: false,
      run: () => editor?.chain().focus().unsetAllMarks().clearNodes().run(),
    },
  ];
  return (
    <div className="ios-card overflow-hidden">
      <div
        role="toolbar"
        aria-label="Text formatting"
        className="flex flex-wrap items-center gap-1 border-b border-white/10 p-2"
      >
        {tools.map((t) => (
          <button
            type="button"
            key={t.label}
            aria-label={t.label}
            aria-pressed={!!t.active}
            title={t.label}
            disabled={disabled || !editor}
            onPointerDown={(e) => e.preventDefault()}
            onClick={t.run}
            className={`rounded-lg p-2.5 transition ${t.active ? "bg-[#c1cdb3]/20 text-[#d5e4c5]" : "text-stone-400 hover:bg-white/5 hover:text-white"}`}
          >
            <t.icon size={16} />
          </button>
        ))}
        <div className="ml-auto flex gap-1">
          <button
            type="button"
            aria-label="Undo"
            disabled={disabled || !editor?.can().undo()}
            onPointerDown={(e) => e.preventDefault()}
            onClick={() => editor?.chain().focus().undo().run()}
            className="rounded-lg p-2 text-stone-400 disabled:opacity-25"
          >
            <Undo2 size={16} />
          </button>
          <button
            type="button"
            aria-label="Redo"
            disabled={disabled || !editor?.can().redo()}
            onPointerDown={(e) => e.preventDefault()}
            onClick={() => editor?.chain().focus().redo().run()}
            className="rounded-lg p-2 text-stone-400 disabled:opacity-25"
          >
            <Redo2 size={16} />
          </button>
        </div>
      </div>
      {editor && (
        <BubbleMenu editor={editor} options={bubbleOptions}>
          <div
            className="flex rounded-xl border border-stone-600 bg-[#202b24] p-1 shadow-xl"
            role="toolbar"
            aria-label="Format selected text"
          >
            {basic.map((t) => (
              <button
                type="button"
                key={t.label}
                aria-label={`Selection ${t.label}`}
                aria-pressed={!!t.active}
                onPointerDown={(e) => e.preventDefault()}
                onClick={t.run}
                className={`rounded-lg p-3 ${t.active ? "bg-white/15 text-white" : "text-stone-300"}`}
              >
                <t.icon size={16} />
              </button>
            ))}
          </div>
        </BubbleMenu>
      )}
      {linkOpen && (
        <div
          className="border-b border-white/10 p-3"
          role="group"
          aria-label="Edit selected text link"
        >
          <label htmlFor="post-link" className="text-xs text-stone-400">
            Link address · leave empty to remove
          </label>
          <div className="mt-2 flex flex-wrap gap-2">
            <input
              id="post-link"
              autoFocus
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  applyLink();
                }
                if (e.key === "Escape") setLinkOpen(false);
              }}
              placeholder="https://example.com"
              className="ios-input flex-1"
            />
            <button
              type="button"
              onClick={applyLink}
              className="ios-btn ios-btn-primary text-xs"
            >
              Apply link
            </button>
            <button
              type="button"
              onClick={() => setLinkOpen(false)}
              className="ios-btn ios-btn-glass text-xs"
            >
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
      <EditorContent editor={editor} />
      <div className="flex flex-wrap justify-between gap-2 border-t border-white/5 px-4 py-3 text-[10px] text-stone-500">
        <span>
          Select text or long-press on mobile to format. No HTML needed.
        </span>
        <span>{visibleLength(value).toLocaleString()} characters</span>
      </div>
    </div>
  );
}
