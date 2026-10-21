"use client";
import { useEffect, useRef, useState } from "react";
import { Palette } from "lucide-react";
import {
  BRAND_KEY,
  parseBrandKits,
  readLogoFile,
  type BrandKit,
} from "@/lib/studio-drafts";
import type { ImageDesign } from "@/lib/image-design";
import { EmptyState } from "./ui";

const CORNERS: { id: ImageDesign["logoCorner"]; label: string }[] = [
  { id: "tl", label: "Top left" },
  { id: "tr", label: "Top right" },
  { id: "bl", label: "Bottom left" },
  { id: "br", label: "Bottom right" },
];

export function BrandKits({
  design,
  onApply,
  disabled = false,
}: {
  design: ImageDesign;
  onApply: (value: Partial<ImageDesign>) => void;
  disabled?: boolean;
}) {
  const [kits, setKits] = useState<BrandKit[]>([]);
  const [name, setName] = useState("");
  const [footer, setFooter] = useState(design.footer);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const logoInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    try {
      setKits(parseBrandKits(JSON.parse(localStorage.getItem(BRAND_KEY) || "[]")));
    } catch {
      setNotice("Brand storage is unavailable.");
    }
  }, []);

  useEffect(() => setFooter(design.footer), [design.footer]);

  function persist(next: BrandKit[]) {
    try {
      localStorage.setItem(BRAND_KEY, JSON.stringify(next));
      setKits(next);
      return true;
    } catch {
      setNotice("Brand kit not saved: browser storage unavailable.");
      return false;
    }
  }

  async function pickLogo(file?: File) {
    if (!file) return;
    setBusy(true);
    setNotice("");
    try {
      const data = await readLogoFile(file);
      onApply({ logoData: data });
      setNotice("Logo added to this design. Save a brand kit to reuse it.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "That logo could not be added.");
    } finally {
      setBusy(false);
    }
  }

  const { logoData, logoCorner, footer: currentFooter } = design;

  return (
    <section className="space-y-2 rounded-xl border border-white/10 p-3">
      <div>
        <h3 className="text-sm font-semibold">Brand kits</h3>
        <p className="ios-caption">
          Colours, font, layout, logo and footer · this browser only. Kits saved before the newer fields still apply
          what they have.
        </p>
      </div>

      <div className="space-y-2 rounded-lg bg-white/[0.03] p-2">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="ios-btn ios-btn-glass text-xs"
            disabled={disabled || busy}
            onClick={() => logoInput.current?.click()}
          >
            {logoData ? "Replace logo" : "Upload logo"}
          </button>
          <select
            aria-label="Logo corner"
            className="ios-input w-auto py-1 text-xs"
            value={logoCorner}
            disabled={disabled || !logoData}
            onChange={(event) => onApply({ logoCorner: event.target.value as ImageDesign["logoCorner"] })}
          >
            {CORNERS.map((corner) => (
              <option key={corner.id} value={corner.id}>
                {corner.label}
              </option>
            ))}
          </select>
          {logoData && (
            <button
              type="button"
              className="ios-pill"
              disabled={disabled}
              onClick={() => onApply({ logoData: "" })}
            >
              Remove logo
            </button>
          )}
        </div>
        <input
          ref={logoInput}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="sr-only"
          aria-label="Upload brand logo"
          onChange={(event) => {
            void pickLogo(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
        <div className="flex flex-wrap items-end gap-2">
          <label className="min-w-0 flex-1 text-xs">
            Export footer
            <input
              className="ios-input mt-1 text-sm"
              aria-label="Export footer"
              placeholder="e.g. @yourchannel"
              value={footer}
              maxLength={160}
              disabled={disabled}
              onChange={(event) => setFooter(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="ios-btn ios-btn-glass text-xs"
            disabled={disabled || footer.trim() === currentFooter}
            onClick={() => onApply({ footer: footer.trim() })}
          >
            Apply footer
          </button>
        </div>
        <p className="ios-caption">
          The footer and logo are painted onto every PNG export, so a downloaded image keeps them.
        </p>
      </div>

      <input
        aria-label="Brand kit name"
        className="ios-input"
        placeholder="Brand kit name"
        value={name}
        maxLength={40}
        disabled={disabled}
        onChange={(event) => setName(event.target.value)}
      />
      <button
        className="ios-btn ios-btn-glass text-xs"
        disabled={disabled || !name.trim() || kits.length >= 20}
        onClick={() => {
          const { background, accent, color, font, ratio, geometry, pattern, align } = design;
          const kit: BrandKit = {
            id: crypto.randomUUID(),
            name: name.trim(),
            background,
            accent,
            color,
            font,
            layout: { ratio, geometry, pattern, align },
            ...(logoData ? { logoData, logoCorner } : {}),
            ...(currentFooter ? { footer: currentFooter } : {}),
          };
          if (persist([kit, ...kits])) {
            setName("");
            setNotice("Brand kit saved with its layout, logo and footer.");
          }
        }}
      >
        Save current brand
      </button>

      {kits.map((kit) => (
        <div key={kit.id} className="flex items-center gap-2">
          <button
            disabled={disabled}
            className="ios-btn ios-btn-glass min-w-0 flex-1 truncate text-xs"
            aria-label={`Apply brand ${kit.name}`}
            onClick={() => {
              onApply({
                background: kit.background,
                accent: kit.accent,
                color: kit.color,
                font: kit.font,
                ...(kit.layout ?? {}),
                logoData: kit.logoData ?? "",
                logoCorner: kit.logoCorner ?? "tl",
                footer: kit.footer ?? "",
              });
              setNotice(`Applied ${kit.name}.`);
            }}
          >
            <span aria-hidden style={{ background: kit.accent }} className="h-3 w-3 rounded-full" />
            {kit.name}
          </button>
          <button
            disabled={disabled}
            className="ios-pill grid min-h-9 min-w-9 place-items-center text-sm"
            aria-label={`Delete brand ${kit.name}`}
            onClick={() => persist(kits.filter((item) => item.id !== kit.id))}
          >
            ×
          </button>
        </div>
      ))}
      {!kits.length && (
        <EmptyState
          compact
          icon={<Palette size={18} />}
          title="No saved brand kits yet"
          hint="Save the current colours, font, logo and footer as a kit, then apply it to any design in one tap."
        />
      )}
      {notice && <p role="status" className="ios-caption">{notice}</p>}
    </section>
  );
}
