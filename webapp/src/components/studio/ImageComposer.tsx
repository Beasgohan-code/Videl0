"use client";
import { useEffect, useRef, useState } from "react";
import {
  Download,
  ImagePlus,
  RotateCcw,
  Undo2,
  Redo2,
  Move,
  Check,
} from "lucide-react";
import {
  ImageDesign,
  initialDesign,
  designSize,
  paintDesign,
  parseDesign,
  designDocument,
} from "@/lib/image-design";
const presets = [
  {
    name: "Editorial",
    background: "#ebe4d5",
    accent: "#8a755b",
    color: "#302c26",
    font: "Georgia" as const,
  },
  {
    name: "Forest",
    background: "#1d3029",
    accent: "#b7c9a3",
    color: "#f4f1e9",
    font: "Georgia" as const,
  },
  {
    name: "Ocean",
    background: "#17313f",
    accent: "#8bc0cd",
    color: "#ecf6f7",
    font: "Arial" as const,
  },
  {
    name: "Studio",
    background: "#26232f",
    accent: "#a99cbf",
    color: "#f5f0fa",
    font: "Arial" as const,
  },
  {
    name: "Terracotta",
    background: "#a45f49",
    accent: "#eac3a3",
    color: "#fff1df",
    font: "Georgia" as const,
  },
];
export function ImageComposer({
  onAttach,
  disabled = false,
}: {
  onAttach: (file: File) => void;
  disabled?: boolean;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const upload = useRef<HTMLInputElement>(null);
  const importInput = useRef<HTMLInputElement>(null);
  const [history, setHistory] = useState<ImageDesign[]>([initialDesign]);
  const [index, setIndex] = useState(0);
  const design = history[index];
  const [selected, setSelected] = useState<"title" | "subtitle" | "label">(
    "title",
  );
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [photo, setPhoto] = useState<HTMLImageElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [attaching, setAttaching] = useState(false);
  const [restored, setRestored] = useState(false);
  useEffect(() => {
    try {
      const saved = localStorage.getItem("videl_image_design_v1");
      if (saved) {
        setHistory([parseDesign(JSON.parse(saved))]);
        setIndex(0);
      }
    } catch {
      setMessage(
        "Saved design could not be restored. Your downloaded designs are unaffected.",
      );
    }
    setRestored(true);
  }, []);
  useEffect(() => {
    if (!restored) return;
    const timer = setTimeout(() => {
      try {
        localStorage.setItem("videl_image_design_v1", designDocument(design));
      } catch {
        setMessage(
          "Browser storage unavailable. Download your design JSON to keep an editable copy.",
        );
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [design, restored]);
  function exportDesign() {
    const url = URL.createObjectURL(
      new Blob([designDocument(design)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "videl-editable-design.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setMessage(
      "Editable design saved. Background photos are not included; keep the original photo separately.",
    );
  }
  async function importDesign(file?: File) {
    if (!file) return;
    try {
      if (file.size > 65536)
        throw new Error("Design files must be smaller than 64 KB.");
      const next = parseDesign(JSON.parse(await file.text()));
      if (
        !window.confirm(
          "Replace this design? Export it first to keep a copy. The current photo will be removed.",
        )
      )
        return;
      change(next);
      setPhotoUrl(null);
      setMessage(
        "Editable design imported. Upload the original background photo if needed.",
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not import this design.",
      );
    }
  }
  const drag = useRef<{
    x: number;
    y: number;
    design: ImageDesign;
    draft: ImageDesign;
  } | null>(null);
  function change(patch: Partial<ImageDesign>) {
    setHistory((current) =>
      [...current.slice(0, index + 1), { ...current[index], ...patch }].slice(
        -60,
      ),
    );
    setIndex(Math.min(index + 1, 59));
    setMessage("");
  }
  const [width, height] = designSize(design.ratio);
  useEffect(() => {
    const ctx = canvas.current?.getContext("2d");
    if (ctx) paintDesign(ctx, design, photo);
  }, [design, photo]);
  useEffect(() => {
    if (!photoUrl) {
      setPhoto(null);
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    const image = new Image();
    image.onload = () => {
      if (active) {
        if (image.naturalWidth * image.naturalHeight > 25000000) {
          setPhotoUrl(null);
          setMessage(
            "Choose a photo under 25 megapixels for reliable editing and publishing.",
          );
        } else {
          setPhoto(image);
        }
        setLoading(false);
      }
    };
    image.onerror = () => {
      if (active) {
        setMessage("That image could not be opened. Try a PNG, JPEG or WebP.");
        setLoading(false);
      }
    };
    image.src = photoUrl;
    return () => {
      active = false;
      URL.revokeObjectURL(photoUrl);
    };
  }, [photoUrl]);
  async function choose(file?: File) {
    if (!file) return;
    if (
      !["image/png", "image/jpeg", "image/webp"].includes(file.type) ||
      file.size > 8 * 1024 * 1024
    ) {
      setMessage("Choose a PNG, JPEG or WebP smaller than 8 MB.");
      return;
    }
    setLoading(true);
    setPhoto(null);
    setPhotoUrl(URL.createObjectURL(file));
    setMessage("");
  }
  function download() {
    canvas.current?.toBlob((blob) => {
      if (!blob) {
        setMessage("Could not export this image.");
        return;
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `videl-design-${width}x${height}.png`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMessage("PNG downloaded. The image is yours to use.");
    }, "image/png");
  }
  function attach() {
    if (!canvas.current || loading) return;
    setAttaching(true);
    canvas.current.toBlob(
      (blob) => {
        setAttaching(false);
        if (!blob) {
          setMessage("Image export failed. Please try again.");
          return;
        }
        if (blob.size > 4 * 1024 * 1024) {
          setMessage(
            "This design is too large to attach. Download the PNG or choose a simpler background.",
          );
          return;
        }
        onAttach(
          new File([blob], "videl-custom-post.jpg", { type: "image/jpeg" }),
        );
        setMessage(
          "Your custom image is attached to the post. Changes here require attaching again.",
        );
      },
      "image/jpeg",
      0.9,
    );
  }
  function point(e: React.PointerEvent<HTMLCanvasElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    return {
      x: ((e.clientX - r.left) / r.width) * 100,
      y: ((e.clientY - r.top) / r.height) * 100,
    };
  }
  function stop(e: React.PointerEvent<HTMLCanvasElement>, cancel = false) {
    if (!drag.current) return;
    const draft = drag.current.draft;
    drag.current = null;
    if (e.currentTarget.hasPointerCapture(e.pointerId))
      e.currentTarget.releasePointerCapture(e.pointerId);
    if (!cancel) change(draft);
    else {
      const ctx = canvas.current?.getContext("2d");
      if (ctx) paintDesign(ctx, design, photo);
    }
  }
  return (
    <section
      className="ios-card mt-5 overflow-hidden"
      aria-label="Custom image designer"
    >
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 p-5">
        <div>
          <p className="post-eyebrow">YOUR IDEAS, YOUR DESIGN</p>
          <h2 className="post-serif mt-2 text-2xl">Image Composer</h2>
          <p className="mt-2 text-xs text-stone-400">
            Edit the words, upload your photo, move the text and make it yours.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            aria-label="Undo design edit"
            disabled={index === 0}
            onClick={() => setIndex((i) => i - 1)}
            className="ios-btn ios-btn-glass !p-2 disabled:opacity-30"
          >
            <Undo2 size={16} />
          </button>
          <button
            aria-label="Redo design edit"
            disabled={index === history.length - 1}
            onClick={() => setIndex((i) => i + 1)}
            className="ios-btn ios-btn-glass !p-2 disabled:opacity-30"
          >
            <Redo2 size={16} />
          </button>
          <button
            onClick={() => {
              if (
                !window.confirm(
                  "Reset the design? Download it first if you want to keep it.",
                )
              )
                return;
              change(initialDesign);
              setPhotoUrl(null);
            }}
            className="ios-btn ios-btn-glass text-xs"
          >
            <RotateCcw size={14} /> Reset
          </button>
        </div>
      </header>
      <div className="grid lg:grid-cols-[300px_minmax(0,1fr)]">
        <div className="order-2 space-y-4 border-t border-white/10 p-5 lg:order-1 lg:border-t-0 lg:border-r">
          <label className="block text-xs text-stone-400">
            Canvas size
            <select
              aria-label="Canvas size"
              value={design.ratio}
              onChange={(e) =>
                change({ ratio: e.target.value as ImageDesign["ratio"] })
              }
              className="ios-input mt-2"
            >
              <option value="landscape">Landscape · 1200 × 675</option>
              <option value="square">Square · 1080 × 1080</option>
              <option value="portrait">Portrait · 1080 × 1350</option>
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            {presets.map((p) => (
              <button
                key={p.name}
                onClick={() => change(p)}
                title={p.name}
                aria-label={`Apply ${p.name} colors and font`}
                className="h-8 w-8 rounded-full border-2 border-white/20"
                style={{ background: p.background }}
              />
            ))}
          </div>
          <label className="block text-xs text-stone-400">
            Heading
            <textarea
              aria-label="Heading"
              rows={2}
              maxLength={300}
              className="ios-input mt-2"
              value={design.title}
              onChange={(e) => change({ title: e.target.value })}
            />
          </label>
          <label className="block text-xs text-stone-400">
            Supporting text
            <textarea
              aria-label="Supporting text"
              rows={2}
              maxLength={600}
              className="ios-input mt-2"
              value={design.subtitle}
              onChange={(e) => change({ subtitle: e.target.value })}
            />
          </label>
          <label className="block text-xs text-stone-400">
            Small label
            <input
              aria-label="Small label"
              maxLength={100}
              className="ios-input mt-2"
              value={design.label}
              onChange={(e) => change({ label: e.target.value })}
            />
          </label>
          <div className="grid grid-cols-3 gap-2">
            {(
              [
                { key: "background", label: "Background" },
                { key: "color", label: "Text" },
                { key: "accent", label: "Accent" },
              ] as const
            ).map((c) => (
              <label key={c.key} className="text-[10px] text-stone-400">
                {c.label}
                <input
                  type="color"
                  value={design[c.key]}
                  aria-label={`${c.label} color`}
                  onChange={(e) => change({ [c.key]: e.target.value })}
                  className="mt-2 h-9 w-full rounded border border-white/10 bg-transparent"
                />
              </label>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-stone-400">
              Typeface
              <select
                aria-label="Typeface"
                value={design.font}
                onChange={(e) =>
                  change({ font: e.target.value as ImageDesign["font"] })
                }
                className="ios-input mt-2"
              >
                <option value="Georgia">Editorial serif</option>
                <option value="Arial">Modern sans</option>
                <option value="monospace">Monospace</option>
              </select>
            </label>
            <label className="text-xs text-stone-400">
              Alignment
              <select
                aria-label="Alignment"
                value={design.align}
                onChange={(e) =>
                  change({
                    align: e.target.value as "left" | "center",
                    titleX: e.target.value === "center" ? 50 : 8,
                    subtitleX: e.target.value === "center" ? 50 : 8,
                    labelX: e.target.value === "center" ? 50 : 8,
                  })
                }
                className="ios-input mt-2"
              >
                <option value="left">Left</option>
                <option value="center">Centered</option>
              </select>
            </label>
          </div>
          <label className="block text-xs text-stone-400">
            Heading size · {design.fontSize}
            <input
              aria-label="Heading size"
              type="range"
              min={24}
              max={140}
              value={design.fontSize}
              onChange={(e) => change({ fontSize: Number(e.target.value) })}
              className="mt-2 w-full accent-[#b5c4a5]"
            />
          </label>
          {(
            [
              {
                key: "subtitleSize",
                label: "Supporting text size",
                min: 12,
                max: 80,
              },
              { key: "labelSize", label: "Label size", min: 10, max: 60 },
            ] as const
          ).map((s) => (
            <label key={s.key} className="block text-xs text-stone-400">
              {s.label} · {Math.round(design[s.key])}
              <input
                aria-label={s.label}
                type="range"
                min={s.min}
                max={s.max}
                value={design[s.key]}
                onChange={(e) => change({ [s.key]: Number(e.target.value) })}
                className="mt-2 w-full accent-[#b5c4a5]"
              />
            </label>
          ))}
          <input
            ref={upload}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={(e) => {
              void choose(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <button
            onClick={() => upload.current?.click()}
            className="ios-btn ios-btn-glass w-full text-xs"
          >
            <ImagePlus size={16} /> Upload background photo
          </button>
          {photoUrl && (
            <>
              <button
                onClick={() => setPhotoUrl(null)}
                className="text-xs text-stone-400 underline"
              >
                Remove photo
              </button>
              {(
                [
                  {
                    key: "overlay",
                    label: "Dark overlay",
                    min: 0,
                    max: 90,
                    step: 1,
                  },
                  {
                    key: "zoom",
                    label: "Photo zoom",
                    min: 1,
                    max: 3,
                    step: 0.05,
                  },
                  {
                    key: "panX",
                    label: "Photo horizontal crop",
                    min: 0,
                    max: 100,
                    step: 1,
                  },
                  {
                    key: "panY",
                    label: "Photo vertical crop",
                    min: 0,
                    max: 100,
                    step: 1,
                  },
                ] as const
              ).map((s) => (
                <label key={s.key} className="block text-[10px] text-stone-400">
                  {s.label}
                  <input
                    aria-label={s.label}
                    type="range"
                    min={s.min}
                    max={s.max}
                    step={s.step}
                    value={design[s.key]}
                    onChange={(e) =>
                      change({ [s.key]: Number(e.target.value) })
                    }
                    className="mt-2 w-full accent-[#b5c4a5]"
                  />
                </label>
              ))}
            </>
          )}
          <label className="flex items-center gap-2 text-xs text-stone-400">
            <input
              type="checkbox"
              checked={design.geometry}
              onChange={(e) => change({ geometry: e.target.checked })}
            />{" "}
            Background geometry (without photo)
          </label>
        </div>
        <div className="order-1 min-w-0 p-4 sm:p-6 lg:order-2">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex gap-2">
              {(["title", "subtitle", "label"] as const).map((layer) => (
                <button
                  key={layer}
                  aria-pressed={selected === layer}
                  onClick={() => setSelected(layer)}
                  className={`rounded-lg border px-3 py-2 text-[10px] ${selected === layer ? "border-[#b5c4a5]/40 bg-[#b5c4a5]/10" : "border-white/10 text-stone-400"}`}
                >
                  {layer === "title"
                    ? "Heading"
                    : layer === "subtitle"
                      ? "Supporting text"
                      : "Label"}
                </button>
              ))}
            </div>
            <span className="flex items-center gap-1 text-[10px] text-stone-500">
              <Move size={12} /> Drag or use arrow keys
            </span>
          </div>
          <div className="flex min-h-56 items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-[#0d120f] p-3">
            <canvas
              ref={canvas}
              tabIndex={0}
              onKeyDown={(e) => {
                const delta = e.shiftKey ? 5 : 1;
                const moves: Record<string, [number, number]> = {
                  ArrowLeft: [-delta, 0],
                  ArrowRight: [delta, 0],
                  ArrowUp: [0, -delta],
                  ArrowDown: [0, delta],
                };
                const move = moves[e.key];
                if (!move) return;
                e.preventDefault();
                change({
                  [`${selected}X`]: Math.max(
                    3,
                    Math.min(90, design[`${selected}X`] + move[0]),
                  ),
                  [`${selected}Y`]: Math.max(
                    5,
                    Math.min(90, design[`${selected}Y`] + move[1]),
                  ),
                });
              }}
              width={width}
              height={height}
              aria-label="Custom post design preview — drag or use arrow keys to move the selected text layer"
              className="h-auto max-h-[650px] w-auto max-w-full cursor-move shadow-xl"
              style={{ touchAction: "none", aspectRatio: `${width}/${height}` }}
              onPointerDown={(e) => {
                const p = point(e);
                drag.current = { ...p, design, draft: design };
                e.currentTarget.setPointerCapture(e.pointerId);
              }}
              onPointerMove={(e) => {
                if (!drag.current) return;
                const p = point(e),
                  start = drag.current;
                const x = Math.max(
                  3,
                  Math.min(90, start.design[`${selected}X`] + p.x - start.x),
                );
                const y = Math.max(
                  5,
                  Math.min(90, start.design[`${selected}Y`] + p.y - start.y),
                );
                const next = {
                  ...start.design,
                  [`${selected}X`]: x,
                  [`${selected}Y`]: y,
                };
                start.draft = next;
                const ctx = e.currentTarget.getContext("2d");
                if (ctx) paintDesign(ctx, next, photo);
              }}
              onPointerUp={(e) => stop(e)}
              onPointerCancel={(e) => stop(e, true)}
            />
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <label className="text-[10px] text-stone-400">
              Selected text horizontal position
              <input
                aria-label="Selected text horizontal position"
                type="range"
                min={3}
                max={90}
                value={design[`${selected}X`]}
                onChange={(e) =>
                  change({ [`${selected}X`]: Number(e.target.value) })
                }
                className="mt-2 w-full accent-[#b5c4a5]"
              />
            </label>
            <label className="text-[10px] text-stone-400">
              Selected text vertical position
              <input
                aria-label="Selected text vertical position"
                type="range"
                min={5}
                max={90}
                value={design[`${selected}Y`]}
                onChange={(e) =>
                  change({ [`${selected}Y`]: Number(e.target.value) })
                }
                className="mt-2 w-full accent-[#b5c4a5]"
              />
            </label>
          </div>
          <p className="mt-4 text-[10px] leading-5 text-stone-500">
            This is the actual export canvas. Keep text inside the edges;
            overflowing lines are clipped. Text, colors and layout autosave on
            this device. Photos are session-only; download the image before
            leaving. No AI or external image service.
          </p>
          <input
            ref={importInput}
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={(e) => {
              void importDesign(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              onClick={exportDesign}
              className="ios-btn ios-btn-glass text-xs"
            >
              Save editable design
            </button>
            <button
              onClick={() => importInput.current?.click()}
              className="ios-btn ios-btn-glass text-xs"
            >
              Import design
            </button>
            <span className="self-center text-[10px] text-stone-500">
              Layout autosaves locally · photos not saved
            </span>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <button
              disabled={loading}
              onClick={download}
              className="ios-btn ios-btn-glass text-xs disabled:opacity-40"
            >
              <Download size={15} /> Download PNG
            </button>
            <button
              disabled={disabled || loading || attaching}
              onClick={attach}
              className="ios-btn ios-btn-primary text-xs disabled:opacity-40"
            >
              <Check size={15} />
              {attaching ? "Preparing image…" : "Use image in post"}
            </button>
          </div>
          {message && (
            <p
              role="status"
              className="mt-4 rounded-xl border border-white/10 p-3 text-xs leading-5 text-stone-300"
            >
              {message}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
