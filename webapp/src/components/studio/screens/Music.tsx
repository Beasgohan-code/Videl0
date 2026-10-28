"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  AudioLines,
  Disc3,
  Heart,
  ListMusic,
  LoaderCircle,
  Music2,
  Pause,
  Play,
  Plus,
  Radio,
  Search,
  SkipBack,
  SkipForward,
  Volume2,
  X,
} from "lucide-react";

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

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("videl-music-favorites") || "[]");
      if (Array.isArray(saved)) setFavorites(saved.filter((id) => typeof id === "string"));
    } catch {
      setFavorites([]);
    }
  }, []);

  useEffect(() => {
    if (audio.current) audio.current.volume = volume;
  }, [volume]);

  async function searchTracks(event?: FormEvent) {
    event?.preventDefault();
    const value = query.trim();
    if (!value || value.length > 120) {
      setError("Type a song, artist, or YouTube link (up to 120 characters). ");
      return;
    }
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
    setFavorites((previous) => {
      const next = previous.includes(track.video_id)
        ? previous.filter((id) => id !== track.video_id)
        : [...previous, track.video_id];
      localStorage.setItem("videl-music-favorites", JSON.stringify(next));
      return next;
    });
  }

  function enqueue(track: Track) {
    setQueue((previous) => [...previous, track]);
  }

  const progress = duration > 0 ? Math.min(100, (time / duration) * 100) : 0;

  return (
    <main className="ios-page ios-page-wide pb-8">
      <audio
        ref={audio}
        preload="none"
        onTimeUpdate={(event) => setTime(event.currentTarget.currentTime)}
        onDurationChange={(event) => setDuration(event.currentTarget.duration || 0)}
        onCanPlay={() => setLoading(false)}
        onPlay={() => { setPlaying(true); setLoading(false); }}
        onPause={() => setPlaying(false)}
        onEnded={playNext}
        onError={() => { setLoading(false); setPlaying(false); if (current) setError("Videl could not prepare this track. Try another one or check downloader health."); }}
      />

      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="ios-caps flex items-center gap-2 text-[11px] text-emerald-200/60">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-300 shadow-[0_0_12px_#6ee7b7]" />
            Videl listening room
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-5xl">Music, in your own space.</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-indigo-100/55">
            Search tracks, build a queue and listen right here. Powered by Videl’s existing music service; no separate VYRON deployment required.
          </p>
        </div>
        <span className="ios-pill ios-pill-green"><Radio size={12} /> Private player</span>
      </header>

      <section className="music-stage mt-7 grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
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

          <div className="mt-5 flex items-center justify-between gap-3">
            <div>
              <p className="ios-caps text-[10px] text-white/35">Listen & discover</p>
              <h2 className="mt-1 text-lg font-semibold">{results.length ? "Search results" : "Find your next track"}</h2>
            </div>
            {results.length > 0 && <span className="text-xs text-white/35">{results.length} results</span>}
          </div>

          {error && <p role="alert" className="mt-4 rounded-xl border border-rose-300/15 bg-rose-400/[0.07] px-4 py-3 text-sm text-rose-100/80">{error}</p>}

          {searching ? (
            <div className="mt-4 flex items-center gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-5 text-sm text-white/50" role="status">
              <LoaderCircle size={18} className="animate-spin text-emerald-200" /> Searching Videl’s music sources…
            </div>
          ) : results.length ? (
            <div className="mt-3 space-y-2">
              {results.map((track, index) => (
                <article key={track.video_id} className="music-track-row group flex items-center gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-2.5 transition hover:border-emerald-200/20 hover:bg-white/[0.045]">
                  <button onClick={() => playTrack(track)} className="relative h-14 w-14 shrink-0 overflow-hidden rounded-xl bg-[#172238]" aria-label={`Play ${track.title}`}>
                    {track.thumbnail ? <img src={track.thumbnail} alt="" loading="lazy" className="h-full w-full object-cover" /> : <Music2 className="m-auto h-full text-white/30" />}
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
              <p className="mt-4 text-sm font-medium text-white/75">A song is only a search away</p>
              <p className="mt-1 max-w-sm text-xs leading-5 text-white/35">Search by title or artist. Your favorites and queue stay in this browser.</p>
            </div>
          )}
        </div>

        <aside className="music-now-panel flex flex-col rounded-3xl border border-emerald-200/10 bg-[linear-gradient(150deg,rgba(22,46,52,.76),rgba(15,20,36,.96)_65%)] p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <span className="ios-caps flex items-center gap-2 text-[10px] text-emerald-100/50"><Disc3 size={14} /> Now playing</span>
            <span className={`h-2 w-2 rounded-full ${playing ? "animate-pulse bg-emerald-300 shadow-[0_0_12px_#6ee7b7]" : "bg-white/20"}`} aria-label={playing ? "Playing" : "Paused"} />
          </div>
          <div className="relative mx-auto mt-5 aspect-square w-full max-w-[260px] overflow-hidden rounded-[26px] border border-white/10 bg-[#111b2c] shadow-2xl shadow-black/30">
            {current?.thumbnail ? <img src={current.thumbnail} alt="" className={`h-full w-full object-cover ${playing ? "scale-100" : "scale-[1.04] opacity-70"} transition duration-700`} /> : <div className="grid h-full place-items-center bg-[radial-gradient(circle_at_35%_25%,rgba(110,231,183,.24),transparent_42%),linear-gradient(145deg,#1a3440,#11162a_60%,#281d38)]"><Disc3 size={72} strokeWidth={1} className="text-emerald-100/65" /></div>}
            <div className="absolute inset-0 bg-gradient-to-t from-black/65 via-transparent to-transparent" />
            <div className="absolute inset-x-0 bottom-0 p-4"><p className="ios-caps text-[9px] text-emerald-100/65">Videl · local player</p><p className="mt-1 line-clamp-2 text-base font-semibold leading-snug">{current?.title || "Ready when you are"}</p></div>
          </div>
          <div className="mt-4 min-h-[42px] text-center">
            <p className="truncate text-sm font-semibold text-white/90">{current?.title || "Pick a track to begin"}</p>
            <p className="mt-1 truncate text-xs text-white/40">{current?.channel || "Your personal listening room"}</p>
          </div>
          <div className="mt-3">
            <input aria-label="Track position" type="range" min={0} max={duration || 1} step={1} value={Math.min(time, duration || 1)} onChange={(event) => { const value = Number(event.target.value); if (audio.current) audio.current.currentTime = value; setTime(value); }} style={{ "--music-progress": `${progress}%` } as React.CSSProperties} className="music-range w-full" />
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
            <div className="flex items-center justify-between"><span className="ios-caps flex items-center gap-2 text-[10px] text-white/45"><ListMusic size={14} /> Up next</span><span className="font-mono text-[10px] text-white/30">{queue.length}</span></div>
            {queue.length ? <div className="mt-2 max-h-40 space-y-1 overflow-y-auto">{queue.map((track, index) => <div key={`${track.video_id}-${index}`} className="flex items-center gap-2 rounded-lg px-2 py-2 text-xs text-white/65"><span className="w-4 shrink-0 font-mono text-[10px] text-white/25">{index + 1}</span><button onClick={() => { setQueue((previous) => previous.filter((_, i) => i !== index)); }} aria-label={`Remove ${track.title} from queue`} className="order-2 rounded p-1 text-white/20 hover:text-rose-200"><X size={13} /></button><button onClick={() => { setQueue((previous) => previous.filter((_, i) => i !== index)); playTrack(track); }} className="min-w-0 flex-1 truncate text-left">{track.title}</button></div>)}</div> : <p className="mt-2 text-xs text-white/30">Add a search result to queue it here.</p>}
          </div>
        </aside>
      </section>
      <p className="mt-5 text-center text-[11px] leading-5 text-white/30">Personal browser playback. Voice-chat streaming remains available through <code className="text-white/45">/play</code> in your Telegram group.</p>
    </main>
  );
}
