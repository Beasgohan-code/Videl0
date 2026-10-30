"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import anime from "animejs";
import {
  AudioLines,
  Disc3,
  Heart,
  ListMusic,
  LoaderCircle,
  Pause,
  Play,
  Plus,
  Radio,
  Search,
  Shuffle,
  SkipBack,
  SkipForward,
  Volume2,
  X,
} from "lucide-react";
import "../music/music.css";
import { VyronCover } from "../music/VyronCover";
import { VyronSeek } from "../music/VyronSeek";
import { useStudio } from "../StudioProvider";

type Track = {
  video_id: string;
  title: string;
  channel: string;
  duration: string;
  thumbnail: string;
};

function clock(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const mins = Math.floor(seconds / 60);
  return `${mins}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

export default function Music() {
  const { tab, open } = useStudio();
  const stageRef = useRef<HTMLElement>(null);
  const logoMarkRef = useRef<SVGSVGElement>(null);
  const coverStageRef = useRef<HTMLDivElement>(null);
  const miniDockRef = useRef<HTMLElement>(null);
  const theatreProgressRef = useRef<{ initialValue: { progress?: number } } | null>(null);
  const audio = useRef<HTMLAudioElement>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Track[]>([]);
  const [queue, setQueue] = useState<Track[]>([]);
  const [current, setCurrent] = useState<Track | null>(null);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [duration, setDuration] = useState(0);
  const [time, setTime] = useState(0);
  const [volume, setVolume] = useState(0.82);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [favoriteTracks, setFavoriteTracks] = useState<Track[]>([]);
  const [history, setHistory] = useState<Track[]>([]);
  const [libraryView, setLibraryView] = useState<"discover" | "favorites" | "history" | "queue">("discover");

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("videl-music-favorites") || "[]");
      const savedTracks = JSON.parse(localStorage.getItem("videl-music-favorite-tracks") || "[]");
      const savedHistory = JSON.parse(localStorage.getItem("videl-music-history") || "[]");
      if (Array.isArray(saved)) setFavorites(saved.filter((id) => typeof id === "string"));
      if (Array.isArray(savedTracks)) setFavoriteTracks(savedTracks.filter((track) => track && typeof track.video_id === "string"));
      if (Array.isArray(savedHistory)) setHistory(savedHistory.filter((track) => track && typeof track.video_id === "string"));
    } catch {
      setFavorites([]);
      setFavoriteTracks([]);
      setHistory([]);
    }
  }, []);

  useEffect(() => {
    if (audio.current) audio.current.volume = volume;
  }, [volume]);

  useEffect(() => {
    if (tab !== "music" || typeof navigator === "undefined" || !("mediaSession" in navigator)) return;
    const session = navigator.mediaSession;
    try {
      session.metadata = current ? new MediaMetadata({
        title: current.title,
        artist: current.channel || "Videl",
        album: "Videl Music",
        artwork: current.thumbnail ? [{ src: current.thumbnail }] : [],
      }) : null;
      session.playbackState = playing ? "playing" : "paused";
      if (duration > 0) session.setPositionState({ duration, position: Math.min(time, duration), playbackRate: audio.current?.playbackRate || 1 });
      session.setActionHandler("play", () => { void audio.current?.play().catch(() => {}); });
      session.setActionHandler("pause", () => audio.current?.pause());
      session.setActionHandler("nexttrack", () => playNext());
      session.setActionHandler("previoustrack", () => {
        if (audio.current) audio.current.currentTime = 0;
        setTime(0);
      });
      session.setActionHandler("seekto", (event) => {
        if (audio.current && typeof event.seekTime === "number") {
          audio.current.currentTime = event.seekTime;
          setTime(event.seekTime);
        }
      });
    } catch {
      // Media Session is optional; keep ordinary in-page controls available.
    }
    return () => {
      for (const action of ["play", "pause", "nexttrack", "previoustrack", "seekto"] as const) {
        try { session.setActionHandler(action, null); } catch { /* Browser does not implement this action. */ }
      }
    };
  }, [tab, current, playing, duration, time, queue]);

  useEffect(() => {
    if (tab !== "music") return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const target = event.target;
      if (target instanceof HTMLElement && (target.isContentEditable || target.closest("input,textarea,select,button,[role=button]"))) return;
      if (event.key === " " && current) {
        event.preventDefault();
        if (playing) audio.current?.pause();
        else void audio.current?.play().catch(() => setError("Tap play again to start audio."));
      } else if ((event.key === "ArrowLeft" || event.key === "ArrowRight") && current && duration > 0) {
        event.preventDefault();
        const next = Math.max(0, Math.min(duration, time + (event.key === "ArrowRight" ? 10 : -10)));
        if (audio.current) audio.current.currentTime = next;
        setTime(next);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [tab, current, playing, duration, time]);

  async function searchTracks(event?: FormEvent) {
    event?.preventDefault();
    const value = query.trim();
    if (!value || value.length > 120) {
      setError("Type a song, artist, or YouTube link (up to 120 characters). ");
      return;
    }
    setLibraryView("discover");
    setSearching(true);
    setError("");
    setResults([]);
    try {
      const response = await fetch(`/api/music/search?q=${encodeURIComponent(value)}`, {
        cache: "no-store",
        signal: AbortSignal.timeout(28000),
      });
      const payload = await response.json();
      if (!response.ok || payload.ok !== true) throw new Error(payload.error || "Search is unavailable right now.");
      setResults(Array.isArray(payload.tracks) ? payload.tracks : []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not search for tracks.");
    } finally {
      setSearching(false);
    }
  }

  function playTrack(track: Track) {
    const player = audio.current;
    if (!player) return;
    setCurrent(track);
    setLibraryView("discover");
    setHistory((previous) => {
      const next = [track, ...previous.filter((item) => item.video_id !== track.video_id)].slice(0, 30);
      localStorage.setItem("videl-music-history", JSON.stringify(next));
      return next;
    });
    setTime(0);
    setDuration(0);
    setLoading(true);
    setError("");
    player.pause();
    player.src = `/api/music/track/${encodeURIComponent(track.video_id)}`;
    player.load();
    void player.play().then(() => setPlaying(true)).catch(() => {
      setPlaying(false);
      setLoading(false);
      setError("The track could not start. Check Videl’s downloader status and try another result.");
    });
  }

  function playNext() {
    if (!queue.length) {
      setPlaying(false);
      setCurrent(null);
      return;
    }
    const [next, ...rest] = queue;
    setQueue(rest);
    playTrack(next);
  }

  function toggleFavorite(track: Track) {
    const isFavorite = favorites.includes(track.video_id);
    setFavorites((previous) => {
      const next = isFavorite
        ? previous.filter((id) => id !== track.video_id)
        : [...previous, track.video_id];
      localStorage.setItem("videl-music-favorites", JSON.stringify(next));
      return next;
    });
    setFavoriteTracks((previous) => {
      const next = isFavorite
        ? previous.filter((item) => item.video_id !== track.video_id)
        : [track, ...previous.filter((item) => item.video_id !== track.video_id)];
      localStorage.setItem("videl-music-favorite-tracks", JSON.stringify(next));
      return next;
    });
  }

  function enqueue(track: Track) {
    setQueue((previous) => [...previous, track]);
  }

  function celebratePlay(target?: HTMLElement) {
    if (!target || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    void import("@mojs/core").then(({ default: mojs }) => {
      const burst = new mojs.Burst({
        parent: target,
        radius: { 0: 48 },
        count: 9,
        children: { shape: "circle", fill: ["#a7f3d0", "#c4b5fd", "#f9a8d4"], radius: { 4: 0 }, duration: 620, easing: "cubic.out" },
      });
      burst.replay();
      window.setTimeout(() => burst.el?.remove(), 900);
    }).catch(() => {});
  }

  function playBatch(shuffle = false, target?: HTMLElement) {
    const tracks = [...displayedTracks];
    if (!tracks.length) return;
    celebratePlay(target);
    if (shuffle) {
      for (let index = tracks.length - 1; index > 0; index -= 1) {
        const swap = Math.floor(Math.random() * (index + 1));
        [tracks[index], tracks[swap]] = [tracks[swap], tracks[index]];
      }
    }
    const [first, ...rest] = tracks;
    setQueue(rest);
    playTrack(first);
  }

  const displayedTracks = libraryView === "favorites"
    ? favoriteTracks
    : libraryView === "history"
      ? history
      : libraryView === "queue"
        ? queue
        : results;
  const sectionTitle = libraryView === "favorites"
    ? "Your favorites"
    : libraryView === "history"
      ? "Recently played"
      : libraryView === "queue"
        ? "Your queue"
        : results.length ? "Search results" : "Find your next track";

  useEffect(() => {
    if (tab !== "music" || !stageRef.current || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const root = stageRef.current;
    const entryNodes = root.querySelectorAll<HTMLElement>("[data-anime-enter]");
    const trackNodes = root.querySelectorAll<HTMLElement>("[data-anime-track]");
    anime.remove(entryNodes);
    anime.remove(trackNodes);
    anime({ targets: entryNodes, opacity: [0, 1], translateY: [18, 0], scale: [0.985, 1], duration: 620, delay: anime.stagger(75), easing: "easeOutExpo" });
    anime({ targets: trackNodes, opacity: [0, 1], translateX: [12, 0], duration: 420, delay: anime.stagger(38, { start: 100 }), easing: "easeOutCubic" });
    return () => { anime.remove(entryNodes); anime.remove(trackNodes); };
  }, [tab, libraryView, displayedTracks.length]);

  useEffect(() => {
    let active = true;
    let unsubscribe = () => {};
    void import("@theatre/core").then(({ getProject, types }) => {
      if (!active) return;
      const project = getProject("Videl Music Motion");
      const sheet = project.sheet("Player stage");
      const progress = sheet.object("Playback progress", { progress: types.number(0) });
      theatreProgressRef.current = progress;
      unsubscribe = progress.onValuesChange(({ progress: value }) => {
        const hue = 150 + Math.max(0, Math.min(1, value)) * 95;
        stageRef.current?.style.setProperty("--theatre-hue", `${hue}deg`);
      });
    }).catch(() => {});
    return () => { active = false; unsubscribe(); theatreProgressRef.current = null; };
  }, []);

  useEffect(() => {
    if (tab !== "music" || !logoMarkRef.current || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let active = true;
    let instance: { stop: () => unknown; reset: () => unknown } | undefined;
    void import("vivus").then(({ default: Vivus }) => {
      if (active && logoMarkRef.current) instance = new Vivus(logoMarkRef.current.id, { duration: 70, type: "oneByOne", start: "autostart" });
    }).catch(() => {});
    return () => { active = false; instance?.stop(); instance?.reset(); };
  }, [tab]);

  useEffect(() => {
    if (tab !== "music" || !current || !coverStageRef.current || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let active = true;
    let tween: { kill: () => void } | undefined;
    void import("gsap").then(({ gsap }) => {
      if (active && coverStageRef.current) tween = gsap.fromTo(coverStageRef.current,
        { autoAlpha: 0.72, scale: 0.94, rotateY: -8, transformPerspective: 900 },
        { autoAlpha: 1, scale: 1, rotateY: 0, duration: 0.68, ease: "power3.out", clearProps: "transform" },
      );
    }).catch(() => {});
    return () => { active = false; tween?.kill(); };
  }, [tab, current?.video_id]);

  useEffect(() => {
    if (tab === "music" || !current || !miniDockRef.current || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let active = true;
    void import("velocity-animate").then(({ default: Velocity }) => {
      if (active && miniDockRef.current) Velocity.animate(miniDockRef.current, { opacity: [1, 0], translateY: [0, 16] }, { duration: 280, easing: "easeOutCubic" });
    }).catch(() => {});
    return () => { active = false; };
  }, [tab, current?.video_id]);

  const audioElement = (
    <audio
      ref={audio}
      preload="none"
      onTimeUpdate={(event) => {
        const player = event.currentTarget;
        const position = player.currentTime || 0;
        if (theatreProgressRef.current && player.duration > 0) {
          theatreProgressRef.current.initialValue = { progress: Math.min(1, position / player.duration) };
        }
        setTime(position);
      }}
      onDurationChange={(event) => setDuration(event.currentTarget.duration || 0)}
      onCanPlay={() => setLoading(false)}
      onPlay={() => { setPlaying(true); setLoading(false); }}
      onPause={() => setPlaying(false)}
      onEnded={playNext}
      onError={() => { setLoading(false); setPlaying(false); if (current) setError("Videl could not prepare this track. Try another one or check downloader health."); }}
    />
  );

  const miniPlayer = current && typeof document !== "undefined" ? createPortal(
        <aside ref={miniDockRef} className="fixed inset-x-3 bottom-[calc(5.25rem+env(safe-area-inset-bottom))] z-50 mx-auto flex max-w-2xl items-center gap-3 rounded-2xl border border-emerald-200/20 bg-[#101a28]/95 p-2.5 shadow-2xl shadow-black/50 backdrop-blur-xl lg:bottom-5" aria-label="Mini music player">
          <button type="button" onClick={() => open("music")} className="h-11 w-11 shrink-0 overflow-hidden rounded-xl" aria-label="Open music player"><VyronCover track={current} className="h-full w-full" rounded={12}/></button>
          <button type="button" onClick={() => open("music")} className="min-w-0 flex-1 text-left"><span className="block truncate text-xs font-semibold text-white/90">{current.title}</span><span className="mt-1 block truncate text-[10px] text-white/45">{current.channel || "Videl Music"} · {playing ? "Playing" : loading ? "Loading" : "Paused"}</span></button>
          <label className="hidden w-28 items-center sm:flex" aria-label="Mini player seek"><input aria-label="Seek track" type="range" min={0} max={duration || 1} step={0.1} value={duration ? Math.min(time, duration) : 0} disabled={!duration} onChange={(event) => { const value = Number(event.target.value); if (audio.current) audio.current.currentTime = value; setTime(value); }} className="music-range w-full"/></label>
          <button type="button" onClick={() => { if (!audio.current) return; if (playing) audio.current.pause(); else void audio.current.play().catch(() => setError("Tap play again to start audio.")); }} aria-label={playing ? "Pause track" : "Resume track"} className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-emerald-200 text-[#06201b]">{loading ? <LoaderCircle size={16} className="animate-spin"/> : playing ? <Pause size={16} fill="currentColor"/> : <Play size={16} fill="currentColor"/>}</button>
          <button type="button" onClick={playNext} aria-label="Skip to next track" className="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-white/60 hover:bg-white/10"><SkipForward size={17}/></button>
        </aside>, document.body,
      ) : null;

  return (
    <div className="contents">
      {audioElement}
      {tab === "music" ? (
        <main ref={stageRef} className="ios-page ios-page-wide pb-8 music-experience">
      <header data-anime-enter className="relative z-10 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="ios-caps flex items-center gap-2 text-[11px] text-emerald-200/60">
            <svg id="videl-music-mark" ref={logoMarkRef} viewBox="0 0 32 24" className="h-5 w-7 overflow-visible" aria-hidden="true"><path d="M2 13h5l3-8 5 15 4-12 3 5h8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
            VIDEL MUSIC
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-5xl">Your music, your space.</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-indigo-100/55">
            An immersive music player built into Videl. Search, queue, and listen with Videl’s own music service.
          </p>
        </div>
        <span className="ios-pill ios-pill-green"><Radio size={12} /> Videl player · browser playback</span>
      </header>

      <section data-anime-enter className="music-stage relative z-10 mt-7 grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0">
          <form onSubmit={searchTracks} className="music-search flex items-center gap-3 rounded-2xl border border-white/10 bg-[#10172a]/80 p-2 pl-4 shadow-2xl shadow-black/20">
            <Search size={19} className="shrink-0 text-emerald-200/70" aria-hidden />
            <label className="sr-only" htmlFor="music-search">Search music</label>
            <input
              id="music-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search a song, artist, or paste a YouTube link…"
              maxLength={120}
              className="min-w-0 flex-1 bg-transparent py-3 text-sm text-white outline-none placeholder:text-white/30"
            />
            <button type="submit" disabled={searching} className="ios-btn ios-btn-primary min-h-10 px-4 text-xs disabled:opacity-60">
              {searching ? <LoaderCircle size={15} className="animate-spin" /> : <Search size={15} />}
              <span className="hidden sm:inline">Search</span>
            </button>
          </form>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="ios-caps text-[10px] text-white/35">Videl library</p>
              <h2 className="mt-1 text-lg font-semibold">{sectionTitle}</h2>
            </div>
            {displayedTracks.length > 0 && <div className="flex gap-2"><button type="button" onClick={(event) => playBatch(false, event.currentTarget)} className="ios-btn ios-btn-glass px-3 py-2 text-[10px]"><Play size={13} fill="currentColor"/> Play all</button><button type="button" onClick={(event) => playBatch(true, event.currentTarget)} className="ios-btn ios-btn-glass px-3 py-2 text-[10px]"><Shuffle size={13}/> Shuffle</button></div>}
            {libraryView === "discover" && results.length > 0 && <span className="text-xs text-white/35">{results.length} results</span>}
          </div>
          <nav aria-label="Music library" className="mt-3 flex flex-wrap gap-2">
            {([["discover", "Discover"], ["favorites", "Liked"], ["history", "Recent"], ["queue", "Queue"]] as const).map(([view, label]) => (
              <button key={view} type="button" onClick={() => setLibraryView(view)} aria-pressed={libraryView === view} className={`rounded-full border px-3 py-1.5 text-[11px] transition ${libraryView === view ? "border-emerald-200/30 bg-emerald-200/10 text-emerald-100" : "border-white/[0.08] text-white/45 hover:bg-white/[0.05] hover:text-white/75"}`}>
                {label}{view === "favorites" ? ` · ${favoriteTracks.length}` : view === "queue" ? ` · ${queue.length}` : view === "history" ? ` · ${history.length}` : ""}
              </button>
            ))}
          </nav>

          {error && <p role="alert" className="mt-4 rounded-xl border border-rose-300/15 bg-rose-400/[0.07] px-4 py-3 text-sm text-rose-100/80">{error}</p>}

          {searching && libraryView === "discover" ? (
            <div className="mt-4 flex items-center gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-5 text-sm text-white/50" role="status">
              <LoaderCircle size={18} className="animate-spin text-emerald-200" /> Searching Videl’s music sources…
            </div>
          ) : displayedTracks.length ? (
            <div className="mt-3 space-y-2">
              {displayedTracks.map((track, index) => (
                <article data-anime-track key={`${track.video_id}-${index}`} className="music-track-row group flex items-center gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-2.5 transition hover:border-emerald-200/20 hover:bg-white/[0.045]">
                  <button onClick={() => playTrack(track)} className="relative h-14 w-14 shrink-0 overflow-hidden rounded-xl bg-[#172238]" aria-label={`Play ${track.title}`}>
                    <VyronCover track={track} className="h-full w-full" rounded={12} />
                    <span className="absolute inset-0 grid place-items-center bg-black/35 text-white opacity-0 transition group-hover:opacity-100"><Play size={17} fill="currentColor" /></span>
                  </button>
                  <button onClick={() => playTrack(track)} className="min-w-0 flex-1 text-left">
                    <span className="block truncate text-sm font-medium text-white/90">{track.title}</span>
                    <span className="mt-1 block truncate text-xs text-white/40">{track.channel || "YouTube"} <span className="px-1">·</span> {track.duration || "—:—"}</span>
                  </button>
                  <span className="hidden w-6 text-center font-mono text-[10px] text-white/25 sm:block">{String(index + 1).padStart(2, "0")}</span>
                  <button onClick={() => toggleFavorite(track)} aria-label={favorites.includes(track.video_id) ? "Remove from favorites" : "Add to favorites"} className={`rounded-lg p-2 transition ${favorites.includes(track.video_id) ? "text-rose-300" : "text-white/30 hover:text-rose-200"}`}>
                    <Heart size={16} fill={favorites.includes(track.video_id) ? "currentColor" : "none"} />
                  </button>
                  <button onClick={() => enqueue(track)} aria-label={`Add ${track.title} to queue`} className="rounded-lg p-2 text-white/35 transition hover:bg-white/5 hover:text-emerald-200"><Plus size={17} /></button>
                </article>
              ))}
            </div>
          ) : (
            <div className="music-empty mt-3 flex min-h-48 flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-5 text-center">
              <span className="grid h-12 w-12 place-items-center rounded-2xl border border-emerald-200/10 bg-emerald-200/[0.06] text-emerald-100/80"><AudioLines size={22} /></span>
              <p className="mt-4 text-sm font-medium text-white/75">{libraryView === "favorites" ? "No liked tracks yet" : libraryView === "history" ? "Nothing played yet" : libraryView === "queue" ? "Your queue is empty" : "A song is only a search away"}</p>
              <p className="mt-1 max-w-sm text-xs leading-5 text-white/35">{libraryView === "discover" ? "Search by title or artist. Likes and recent plays stay in this browser; the queue lasts for this session." : "Search or discover a track, then add it to this part of your library."}</p>
            </div>
          )}
        </div>

        <aside className="music-now-panel flex flex-col rounded-3xl border border-emerald-200/10 bg-[linear-gradient(150deg,rgba(22,46,52,.76),rgba(15,20,36,.96)_65%)] p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <span className="ios-caps flex items-center gap-2 text-[10px] text-emerald-100/50"><Disc3 size={14} /> Now playing</span>
            <span className={`h-2 w-2 rounded-full ${playing ? "animate-pulse bg-emerald-300 shadow-[0_0_12px_#6ee7b7]" : "bg-white/20"}`} aria-label={playing ? "Playing" : "Paused"} />
          </div>
          <div ref={coverStageRef} className="music-cover-glow relative mx-auto mt-5 aspect-square w-full max-w-[260px] overflow-hidden rounded-[26px] border border-white/10 bg-[#111b2c] shadow-2xl shadow-black/30">
            <VyronCover track={current} className={`h-full w-full transition duration-700 ${playing ? "scale-100" : "scale-[1.04] opacity-70"}`} rounded={26} />
            <div className="absolute inset-0 bg-gradient-to-t from-black/65 via-transparent to-transparent" />
            <div className="absolute inset-x-0 bottom-0 p-4"><p className="ios-caps text-[9px] text-emerald-100/65">Videl · local player</p><p className="mt-1 line-clamp-2 text-base font-semibold leading-snug">{current?.title || "Ready when you are"}</p></div>
          </div>
          <div className="mt-4 min-h-[42px] text-center">
            <p className="truncate text-sm font-semibold text-white/90">{current?.title || "Pick a track to begin"}</p>
            <p className="mt-1 truncate text-xs text-white/40">{current?.channel || "Your personal listening room"}</p>
          </div>
          <div className="mt-3">
            <VyronSeek trackKey={current?.video_id ?? "idle"} position={time} duration={duration} onSeek={(value) => { if (audio.current) audio.current.currentTime = value; setTime(value); }} />
            <div className="mt-1 flex justify-between font-mono text-[10px] text-white/35"><span>{clock(time)}</span><span>{clock(duration)}</span></div>
          </div>
          <div className="mt-2 flex items-center justify-center gap-5">
            <button onClick={() => { if (audio.current) audio.current.currentTime = 0; }} aria-label="Restart track" className="rounded-full p-2 text-white/45 hover:text-white"><SkipBack size={18} fill="currentColor" /></button>
            <button onClick={() => { if (!audio.current) return; if (playing) audio.current.pause(); else void audio.current.play().catch(() => setError("Tap play again to start audio.")); }} disabled={!current || loading} aria-label={playing ? "Pause" : "Play"} className="grid h-12 w-12 place-items-center rounded-full bg-emerald-200 text-[#06201b] shadow-[0_5px_24px_rgba(110,231,183,.22)] transition hover:scale-105 disabled:opacity-40">
              {loading ? <LoaderCircle size={18} className="animate-spin" /> : playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" className="ml-0.5" />}
            </button>
            <button onClick={playNext} aria-label="Play next track" className="rounded-full p-2 text-white/45 hover:text-white"><SkipForward size={18} fill="currentColor" /></button>
          </div>
          <div className="mt-4 flex items-center gap-2 text-white/45"><Volume2 size={14} /><input aria-label="Volume" type="range" min={0} max={1} step={0.01} value={volume} onChange={(event) => setVolume(Number(event.target.value))} className="music-range flex-1" /><span className="w-8 text-right font-mono text-[10px]">{Math.round(volume * 100)}%</span></div>
          <div className="mt-5 border-t border-white/[0.08] pt-4">
            <div className="flex items-center justify-between"><span className="ios-caps flex items-center gap-2 text-[10px] text-white/45"><ListMusic size={14} /> Up next</span><div className="flex items-center gap-2"><span className="font-mono text-[10px] text-white/30">{queue.length}</span>{queue.length > 0 && <button type="button" onClick={() => setQueue([])} className="text-[10px] text-white/35 hover:text-rose-200">Clear queue</button>}</div></div>
            {queue.length ? <div className="mt-2 max-h-40 space-y-1 overflow-y-auto">{queue.map((track, index) => <div key={`${track.video_id}-${index}`} className="flex items-center gap-2 rounded-lg px-2 py-2 text-xs text-white/65"><span className="w-4 shrink-0 font-mono text-[10px] text-white/25">{index + 1}</span><button onClick={() => { setQueue((previous) => previous.filter((_, i) => i !== index)); }} aria-label={`Remove ${track.title} from queue`} className="order-2 rounded p-1 text-white/20 hover:text-rose-200"><X size={13} /></button><button onClick={() => { setQueue((previous) => previous.filter((_, i) => i !== index)); playTrack(track); }} className="min-w-0 flex-1 truncate text-left">{track.title}</button></div>)}</div> : <p className="mt-2 text-xs text-white/30">Add a search result to queue it here.</p>}
          </div>
        </aside>
      </section>
      <p className="mt-5 text-center text-[11px] leading-5 text-white/30">Personal browser playback. Voice-chat streaming remains available through <code className="text-white/45">/play</code> in your Telegram group.</p>
        </main>
      ) : miniPlayer}
    </div>
  );
}
