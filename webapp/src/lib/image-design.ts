export type ImageDesign = {
  ratio: "landscape" | "square" | "portrait";
  title: string;
  subtitle: string;
  label: string;
  background: string;
  accent: string;
  color: string;
  font: "Georgia" | "Arial" | "monospace";
  fontSize: number;
  subtitleSize: number;
  labelSize: number;
  labelX: number;
  labelY: number;
  align: "left" | "center";
  titleX: number;
  titleY: number;
  subtitleX: number;
  subtitleY: number;
  overlay: number;
  zoom: number;
  panX: number;
  panY: number;
  geometry: boolean;
};
export const initialDesign: ImageDesign = {
  ratio: "landscape",
  title: "Make it yours.",
  subtitle: "Your words. Your community. Your next great post.",
  label: "COMMUNITY UPDATE",
  background: "#1d3029",
  accent: "#b7c9a3",
  color: "#f4f1e9",
  font: "Georgia",
  fontSize: 84,
  subtitleSize: 28.8,
  labelSize: 16.8,
  labelX: 8,
  labelY: 9,
  align: "left",
  titleX: 8,
  titleY: 32,
  subtitleX: 8,
  subtitleY: 72,
  overlay: 35,
  zoom: 1,
  panX: 50,
  panY: 50,
  geometry: true,
};
export function designSize(ratio: ImageDesign["ratio"]) {
  return ratio === "square"
    ? [1080, 1080]
    : ratio === "portrait"
      ? [1080, 1350]
      : [1200, 675];
}
export function wrapDesignText(
  text: string,
  maxWidth: number,
  measure: (text: string) => number,
) {
  const lines: string[] = [];
  for (const paragraph of text.split("\n")) {
    if (!paragraph) {
      lines.push("");
      continue;
    }
    let line = "";
    for (const word of paragraph.split(/\s+/)) {
      const proposed = line ? `${line} ${word}` : word;
      if (measure(proposed) <= maxWidth) {
        line = proposed;
        continue;
      }
      if (line) {
        lines.push(line);
        line = "";
      }
      for (const char of word) {
        if (line && measure(line + char) > maxWidth) {
          lines.push(line);
          line = "";
        }
        line += char;
      }
    }
    lines.push(line);
  }
  return lines;
}
export function paintDesign(
  ctx: CanvasRenderingContext2D,
  d: ImageDesign,
  photo: HTMLImageElement | null,
) {
  const [w, h] = designSize(d.ratio);
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = d.background;
  ctx.fillRect(0, 0, w, h);
  if (photo) {
    const scale =
      Math.max(w / photo.naturalWidth, h / photo.naturalHeight) * d.zoom;
    const iw = photo.naturalWidth * scale,
      ih = photo.naturalHeight * scale;
    ctx.drawImage(
      photo,
      ((w - iw) * d.panX) / 100,
      ((h - ih) * d.panY) / 100,
      iw,
      ih,
    );
    ctx.fillStyle = `rgba(0,0,0,${d.overlay / 100})`;
    ctx.fillRect(0, 0, w, h);
  } else if (d.geometry) {
    ctx.save();
    ctx.strokeStyle = d.accent;
    ctx.globalAlpha = 0.28;
    ctx.lineWidth = 2;
    for (let i = 0; i < 5; i++) {
      ctx.beginPath();
      ctx.arc(w * 0.91, h * 0.38, w * (0.16 + i * 0.035), 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.fillStyle = d.accent;
    ctx.globalAlpha = 0.08;
    ctx.fillRect(w * 0.72, 0, w * 0.28, h);
    ctx.restore();
  }
  ctx.save();
  ctx.fillStyle = d.color;
  ctx.textAlign = d.align;
  ctx.textBaseline = "top";

  function layer(
    text: string,
    x: number,
    y: number,
    size: number,
    font: string,
  ) {
    ctx.font = `${size}px ${font}`;
    const px = (w * x) / 100,
      py = (h * y) / 100;
    const width =
      d.align === "center"
        ? Math.min(px, w - px) * 2 - w * 0.08
        : w - px - w * 0.05;
    const lines = wrapDesignText(
      text,
      Math.max(w * 0.1, width),
      (t) => ctx.measureText(t).width,
    );
    const maxLines = Math.max(
      1,
      Math.floor((h - py - h * 0.04) / (size * 1.2)),
    );
    lines
      .slice(0, maxLines)
      .forEach((line, i) => ctx.fillText(line, px, py + i * size * 1.2));
  }
  ctx.globalAlpha = 0.75;
  layer(d.label, d.labelX, d.labelY, (d.labelSize * w) / 1200, "Arial");
  ctx.globalAlpha = 1;
  layer(d.title, d.titleX, d.titleY, (d.fontSize * w) / 1200, d.font);
  ctx.globalAlpha = 0.82;
  layer(
    d.subtitle,
    d.subtitleX,
    d.subtitleY,
    (d.subtitleSize * w) / 1200,
    "Arial",
  );
  ctx.restore();
}

/** Versioned, bounded design documents; never trust imported JSON or browser storage. */
export function parseDesign(value: unknown): ImageDesign {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Choose a valid Videl design JSON file.");
  const doc = value as Record<string, unknown>;
  if (doc.version !== undefined && doc.version !== 1)
    throw new Error("This design version is not supported.");
  const input = (doc.design ?? doc) as Record<string, unknown>;
  if (
    !input ||
    typeof input !== "object" ||
    Array.isArray(input) ||
    typeof input.title !== "string"
  )
    throw new Error("Invalid design document.");
  const result = { ...initialDesign };
  for (const key of ["title", "subtitle", "label"] as const)
    if (typeof input[key] === "string")
      result[key] = input[key].slice(
        0,
        key === "subtitle" ? 600 : key === "title" ? 300 : 100,
      );
  for (const key of ["background", "accent", "color"] as const)
    if (typeof input[key] === "string" && /^#[0-9a-f]{6}$/i.test(input[key]))
      result[key] = input[key];
  if (["landscape", "square", "portrait"].includes(String(input.ratio)))
    result.ratio = input.ratio as ImageDesign["ratio"];
  if (["Georgia", "Arial", "monospace"].includes(String(input.font)))
    result.font = input.font as ImageDesign["font"];
  if (input.align === "left" || input.align === "center")
    result.align = input.align;
  if (typeof input.geometry === "boolean") result.geometry = input.geometry;
  const ranges = {
    fontSize: [24, 140],
    subtitleSize: [12, 80],
    labelSize: [10, 60],
    titleX: [3, 90],
    subtitleX: [3, 90],
    labelX: [3, 90],
    titleY: [5, 90],
    subtitleY: [5, 90],
    labelY: [5, 90],
    overlay: [0, 90],
    zoom: [1, 3],
    panX: [0, 100],
    panY: [0, 100],
  } as const;
  for (const key of Object.keys(ranges) as (keyof typeof ranges)[]) {
    const n = input[key];
    if (typeof n === "number" && Number.isFinite(n))
      result[key] = Math.min(ranges[key][1], Math.max(ranges[key][0], n));
  }
  return result;
}
export function designDocument(design: ImageDesign) {
  return JSON.stringify({ version: 1, design: parseDesign(design) }, null, 2);
}
