"use client";
import { useEffect, useMemo, useState, useRef } from "react";
import { ArrowDownToLine, Check, ImagePlus, Search, Trash2, Upload, Sparkles, Heart } from "lucide-react";
import { POST_ASSETS, POST_ASSET_CATEGORIES } from "@/lib/post-assets";

const STORAGE_KEY = "videl_custom_assets_v1";

type CustomAsset = { id: string; title: string; category: string; dataUrl: string; createdAt: string };
type Collection = "Covers" | "Stories" | "Quote cards";

const COLLECTIONS: { key: Collection; aspect: "16:9" | "4:5" | "1:1"; blurb: string }[] = [
  { key: "Covers", aspect: "16:9", blurb: "Wide covers for posts and channels" },
  { key: "Stories", aspect: "4:5", blurb: "Tall cards for events and launches" },
  { key: "Quote cards", aspect: "1:1", blurb: "Square statements worth sharing" },
];

export function PostAssetLibrary({
  selected,
  onSelect,
  disabled = false,
}: {
  selected: string;
  onSelect: (path: string) => void;
  disabled?: boolean;
}) {
  const [category, setCategory] = useState("All");
  const [search, setSearch] = useState("");
  const [custom, setCustom] = useState<CustomAsset[]>([]);
  const [notice, setNotice] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<"collection" | "yours">("collection");
  const [collection, setCollection] = useState<Collection>("Covers");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setCustom(JSON.parse(saved));
    } catch {}
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(custom));
    } catch {
      setNotice("Storage full — delete some custom assets.");
    }
  }, [custom]);

  function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      setNotice("Use PNG, JPEG or WebP.");
      return;
    }
    if (file.size > 1.5 * 1024 * 1024) {
      setNotice("Max 1.5 MB per asset so it fits browser storage. Compress first.");
      return;
    }
    if (custom.length >= 10) {
      setNotice("You have 10 custom assets — delete one to add more.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result);
      const asset: CustomAsset = {
        id: crypto.randomUUID(),
        title: file.name.replace(/\.[^.]+$/, "").slice(0, 40) || "My image",
        category: "Your assets",
        dataUrl,
        createdAt: new Date().toISOString(),
      };
      setCustom((value) => [asset, ...value]);
      setTab("yours");
      setNotice(`“${asset.title}” added to Your Assets ✨`);
    };
    reader.readAsDataURL(file);
  }
  function deleteCustom(id: string) {
    if (!confirm("Delete this custom asset from this browser? This cannot be undone.")) return;
    setCustom((value) => value.filter((asset) => asset.id !== id));
  }

  const activeCollection = COLLECTIONS.find((item) => item.key === collection)!;
  const categories = useMemo(
    () => ["All", ...new Set(POST_ASSETS.filter((asset) => asset.aspect === activeCollection.aspect).map((asset) => asset.category))],
    [activeCollection.aspect],
  );
  const filtered = POST_ASSETS.filter(
    (asset) =>
      asset.aspect === activeCollection.aspect &&
      (category === "All" || asset.category === category) &&
      `${asset.title} ${asset.category}`.toLowerCase().includes(search.toLowerCase()),
  );
  const filteredCustom = custom.filter(
    (asset) => `${asset.title} ${asset.category}`.toLowerCase().includes(search.toLowerCase()) && (category === "All" || category === "Your assets"),
  );
  const counts = (aspect: string) => POST_ASSETS.filter((asset) => asset.aspect === aspect).length;

  return (
    <section className="post-asset-library mt-5" aria-label="Image library">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="post-eyebrow">THE VIDEL IMAGE LIBRARY</p>
          <h2 className="post-serif mt-2 text-2xl">A good story deserves a good image.</h2>
          <p className="mt-2 text-xs leading-5 text-stone-400">
            {POST_ASSETS.length} original PNG assets — covers, stories and quote cards — plus{" "}
            <span className="text-[#b5c4a5]">your own uploads</span>. Attach one, download it, or use it as a starting point.
          </p>
        </div>
        <label className="relative">
          <Search size={14} className="absolute left-3 top-3.5 text-stone-400" />
          <input
            aria-label="Search image library"
            className="ios-input !pl-9 text-xs"
            placeholder="Find an image…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <div className="flex rounded-full border border-white/10 bg-white/[0.03] p-1">
          <button
            onClick={() => setTab("collection")}
            aria-pressed={tab === "collection"}
            className={`rounded-full px-4 py-2 text-xs font-semibold transition ${tab === "collection" ? "bg-[#b5c4a5] text-[#151b18]" : "text-stone-400"}`}
          >
            Collection · {POST_ASSETS.length}
          </button>
          <button
            onClick={() => setTab("yours")}
            aria-pressed={tab === "yours"}
            className={`rounded-full px-4 py-2 text-xs font-semibold transition ${tab === "yours" ? "bg-[#b5c4a5] text-[#151b18]" : "text-stone-400"}`}
          >
            Your Assets · {custom.length}
          </button>
        </div>
        <button onClick={() => fileRef.current?.click()} className="ios-btn ios-btn-primary text-xs !py-2">
          <Upload size={14} /> Upload Your Own
        </button>
        <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={handleUpload} />
        <span className="text-[10px] text-stone-500">PNG/JPEG/WebP · 1.5 MB · up to 10 · stored in this browser</span>
      </div>
      {notice && (
        <p role="status" className="mt-3 rounded-xl bg-[#b5c4a5]/10 px-3 py-2 text-xs text-[#c5d6b3]">
          {notice}
        </p>
      )}

      {tab === "collection" && (
        <div className="mt-4 grid gap-2 sm:grid-cols-3" role="tablist" aria-label="Image collections">
          {COLLECTIONS.map((item) => (
            <button
              key={item.key}
              role="tab"
              aria-selected={collection === item.key}
              onClick={() => {
                setCollection(item.key);
                setCategory("All");
              }}
              className={`rounded-xl border px-4 py-3 text-left transition ${collection === item.key ? "border-[#b5c4a5]/50 bg-[#b5c4a5]/10" : "border-white/10 bg-white/[0.02] hover:border-white/20"}`}
            >
              <span className="flex items-center justify-between text-xs font-semibold text-stone-200">
                {item.key}
                <span className="font-mono text-[10px] text-stone-500">{counts(item.aspect)}</span>
              </span>
              <span className="mt-1 block text-[10px] leading-4 text-stone-500">{item.blurb}</span>
            </button>
          ))}
        </div>
      )}

      <div className="my-4 flex flex-wrap gap-2">
        {(tab === "yours" ? ["All", "Your assets"] : categories).map((value) => (
          <button
            key={value}
            aria-pressed={category === value}
            onClick={() => setCategory(value)}
            className={`rounded-full border px-3 py-1.5 text-[11px] transition ${value === category ? "border-[#b5c4a5]/40 bg-[#b5c4a5]/15 text-[#d7e2ca]" : "border-white/10 text-stone-400 hover:text-white"}`}
          >
            {value}
          </button>
        ))}
      </div>

      {tab === "yours" &&
        (custom.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/15 bg-white/[0.02] p-10 text-center">
            <Sparkles size={28} className="mx-auto text-[#b5c4a5]/50" />
            <h3 className="mt-3 text-sm font-semibold">No custom assets yet</h3>
            <p className="mx-auto mt-2 max-w-sm text-xs leading-5 text-stone-400">
              Upload your own PNG/JPEG images — logos, photos, brand backgrounds. They stay in this browser (localStorage), up to 10 images of
              1.5 MB, and you can use them instantly as post images.
            </p>
            <button onClick={() => fileRef.current?.click()} className="ios-btn ios-btn-glass mt-4 text-xs">
              <ImagePlus size={14} /> Choose an image
            </button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {filteredCustom.map((asset) => {
              const active = selected === asset.dataUrl;
              return (
                <article key={asset.id} className={`overflow-hidden rounded-2xl border bg-[#1c201e] ${active ? "border-[#b5c4a5]/60" : "border-white/10"}`}>
                  <button disabled={disabled} onClick={() => onSelect(asset.dataUrl)} className="group block w-full overflow-hidden disabled:opacity-40" aria-label={`Use ${asset.title}`}>
                    <img src={asset.dataUrl} alt={`${asset.title} custom image`} width={1200} height={675} loading="lazy" className="aspect-video w-full object-cover transition duration-300 group-hover:scale-[1.03]" />
                  </button>
                  <div className="flex items-center justify-between gap-3 p-4">
                    <div>
                      <p className="text-[9px] uppercase tracking-[.15em] text-[#b5c4a5]">Your assets · {new Date(asset.createdAt).toLocaleDateString()}</p>
                      <h3 className="mt-1 text-xs font-medium text-stone-200">{asset.title}</h3>
                    </div>
                    <div className="flex gap-1">
                      <a href={asset.dataUrl} download={`${asset.title}.png`} aria-label={`Download ${asset.title}`} className="rounded-lg p-2 text-stone-400 hover:bg-white/5 hover:text-white">
                        <ArrowDownToLine size={15} />
                      </a>
                      <button disabled={disabled} onClick={() => onSelect(asset.dataUrl)} aria-label={`Attach ${asset.title}`} className="rounded-lg bg-[#b5c4a5]/10 p-2 text-[#c5d6b3] disabled:opacity-40">
                        {active ? <Check size={15} /> : <ImagePlus size={15} />}
                      </button>
                      <button onClick={() => deleteCustom(asset.id)} aria-label={`Delete ${asset.title}`} className="rounded-lg p-2 text-rose-300 hover:bg-rose-500/10">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        ))}

      {tab === "collection" && filtered.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((asset) => {
            const active = selected.endsWith(asset.file);
            return (
              <article key={asset.id} className={`overflow-hidden rounded-2xl border bg-[#1c201e] ${active ? "border-[#b5c4a5]/60" : "border-white/10"}`}>
                <button disabled={disabled} onClick={() => onSelect(asset.file)} className="group block w-full overflow-hidden disabled:opacity-40" aria-label={`Use ${asset.title}`}>
                  <img
                    src={asset.file}
                    alt={`${asset.title} — ${asset.category.toLowerCase()} image`}
                    width={1200}
                    height={675}
                    loading="lazy"
                    className={`w-full object-cover transition duration-300 group-hover:scale-[1.03] ${asset.aspect === "4:5" ? "aspect-[4/5]" : asset.aspect === "1:1" ? "aspect-square" : "aspect-video"}`}
                  />
                </button>
                <div className="flex items-center justify-between gap-3 p-4">
                  <div className="min-w-0">
                    <p className="text-[9px] uppercase tracking-[.15em] text-stone-500">
                      {asset.category} · {asset.aspect}
                    </p>
                    <h3 className="mt-1 truncate text-xs font-medium text-stone-200">{asset.title}</h3>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <a href={asset.file} download={`${asset.id}.png`} aria-label={`Download ${asset.title}`} className="rounded-lg p-2 text-stone-400 hover:bg-white/5 hover:text-white">
                      <ArrowDownToLine size={15} />
                    </a>
                    <button disabled={disabled} onClick={() => onSelect(asset.file)} aria-label={`Attach ${asset.title}`} className="rounded-lg bg-[#b5c4a5]/10 p-2 text-[#c5d6b3] disabled:opacity-40">
                      {active ? <Check size={15} /> : <ImagePlus size={15} />}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
      {tab === "collection" && !filtered.length && (
        <p role="status" className="rounded-xl border border-white/10 p-6 text-sm text-stone-400">
          No images match your search. Try another category.
        </p>
      )}
      <p className="mt-4 flex items-center gap-2 text-[10px] leading-5 text-stone-500">
        <Heart size={12} className="text-[#b5c4a5]/60" /> Original Videl artwork, generated locally by scripts/create_post_assets.py · your uploads stay in this
        browser · attach or download anytime.
      </p>
    </section>
  );
}
