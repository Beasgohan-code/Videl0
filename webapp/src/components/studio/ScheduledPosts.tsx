"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { CalendarClock, Pause, Play, SkipForward } from "lucide-react";
import type { ButtonRow } from "@/lib/post-buttons";
import {
  describeInZone,
  deviceTimezone,
  nextSeriesRun,
  timezoneOptions,
  wallInputOf,
  zonedWallToUtc,
} from "@/lib/schedule-time";
import { Callout, EmptyState, LoadingState } from "./ui";

type Job = {
  id: string;
  status: string;
  chat_id: string;
  scheduled_at: string;
  text: string;
  message_id?: number;
  attempts?: number;
  repeat?: string | null;
  sent_count?: number;
  skipped?: number;
  error?: string | null;
  finished_at?: string | null;
  timezone?: string | null;
  paused?: boolean;
  dst_adjusted?: boolean;
};
type Repeat = "once" | "daily" | "weekly";

const STATUS_COPY: Record<string, string> = {
  pending: "Queued",
  sending: "Sending now",
  sent: "Delivered",
  failed: "Rejected by Telegram",
  unconfirmed: "Outcome unknown",
  missed: "Missed (over a day late)",
  cancelled: "Cancelled",
};
const REPEAT_COPY: Record<string, string> = { daily: "Every day", weekly: "Every week" };
const STATUS_HELP: Record<string, string> = {
  pending: "Waiting for its scheduled time.",
  sending: "The bot has claimed this job and is calling the Bot API.",
  sent: "Telegram accepted the message.",
  failed: "Telegram refused it. Nothing was delivered, so a retry is safe.",
  unconfirmed: "The bot could not confirm delivery. Check Telegram before resending anything.",
  missed: "The bot was offline for more than a day past the due time; it is never sent late.",
  cancelled: "Cancelled before it was due.",
};

export function ScheduledPosts({
  chatId,
  text,
  mediaUrl,
  buttons,
  hasLocalImage,
  reviewed,
  disabled,
}: {
  chatId: string;
  text: string;
  mediaUrl: string;
  buttons: ButtonRow[];
  hasLocalImage: boolean;
  reviewed: boolean;
  disabled: boolean;
}) {
  // The device zone is only knowable in the browser. Start from UTC so the
  // server and the first client render agree, then upgrade once mounted.
  const [zone, setZone] = useState("UTC");
  const [zones, setZones] = useState<string[]>(["UTC"]);
  useEffect(() => {
    const detected = deviceTimezone();
    setZone(detected);
    setZones(timezoneOptions(detected));
  }, []);
  const [repeat, setRepeat] = useState<Repeat>("once");
  const [date, setDate] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [notice, setNotice] = useState("");
  const [noticeOk, setNoticeOk] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  // A copy is a brand-new post: it needs its own time, never the original's.
  const [copyFor, setCopyFor] = useState("");
  const [copyWhen, setCopyWhen] = useState("");
  const request = useRef<{ fingerprint: string; id: string } | null>(null);

  const repeats = repeat !== "once";
  const instant = date ? zonedWallToUtc(date, zone) : null;
  const wallClock = date.slice(11, 16);
  const preview = useMemo(
    () =>
      date && repeats
        ? nextSeriesRun(date, zone, repeat as "daily" | "weekly")
        : null,
    [date, repeats, repeat, zone],
  );

  async function refresh() {
    const response = await fetch("/api/schedules", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "Queue unavailable");
    setJobs(data.jobs);
    setLoaded(true);
  }

  function say(message: string) {
    setNoticeOk(true);
    setNotice(message);
  }

  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setNotice("");
    try {
      await action();
    } catch (error) {
      setNoticeOk(false);
      setNotice((error as Error).message);
      setLoaded(true);
    } finally {
      setBusy(false);
    }
  }

  // The queue is the point of this panel: read it once it is on screen instead
  // of waiting for someone to press Refresh.
  useEffect(() => {
    void run(refresh);
  }, []);

  async function schedule() {
    if (disabled) return;
    if (!instant) throw new Error(`Choose a valid time in ${zone}.`);
    if (Date.parse(instant.iso) < Date.now() + 60_000)
      throw new Error("Choose a time at least a minute ahead.");
    const when = describeInZone(instant.iso, zone);
    const summary = `${when}${repeats ? ` and repeat it ${REPEAT_COPY[repeat].toLowerCase()}, keeping ${wallClock} local time` : ""}`;
    if (!window.confirm(`Schedule the current post to ${chatId} at ${summary}?`)) return;
    const snapshot = {
      chat_id: chatId.trim(),
      text,
      media_url: mediaUrl.trim(),
      buttons,
      schedule_at: instant.iso,
    };
    const fingerprint = JSON.stringify({ ...snapshot, repeat, timezone: zone, wall: repeats ? wallClock : "" });
    if (request.current?.fingerprint !== fingerprint)
      request.current = { fingerprint, id: crypto.randomUUID() };
    const response = await fetch("/api/schedules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...snapshot,
        request_id: request.current.id,
        repeat: repeats ? repeat : undefined,
        timezone: zone,
        wall_time: repeats ? wallClock : undefined,
      }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok)
      throw new Error(data.error || "Schedule unconfirmed. Refresh before retrying.");
    say(`Schedule ${data.status}: ${data.job_id}`);
    await refresh();
  }

  async function series(job: Job, action: "pause" | "resume" | "skip") {
    await run(async () => {
      if (
        action === "skip" &&
        !window.confirm(
          "Skip the next occurrence of this series? The occurrence after it stays scheduled.",
        )
      )
        return;
      const response = await fetch("/api/schedules/series", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: job.id, action }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok)
        throw new Error(data.error || "Series change unconfirmed; refresh the queue.");
      say(
        action === "pause"
          ? "Series paused. Nothing will send until it is resumed."
          : action === "resume"
            ? `Series resumed: next run ${describeInZone(data.scheduled_at, job.timezone)}.`
            : `Next occurrence skipped. It now runs ${describeInZone(data.scheduled_at, job.timezone)}.`,
      );
      await refresh();
    });
  }

  async function cancel(job: Job) {
    await run(async () => {
      if (!window.confirm("Cancel this scheduled post?")) return;
      const response = await fetch("/api/schedules", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: job.id }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok)
        throw new Error(data.error || "Cancellation unconfirmed; refresh.");
      await refresh();
    });
  }

  async function retry(job: Job) {
    await run(async () => {
      if (!window.confirm("Requeue this rejected post? Telegram refused it, so nothing was delivered."))
        return;
      const response = await fetch("/api/schedules/retry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: job.id }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok)
        throw new Error(data.error || "Requeue unconfirmed; refresh.");
      say(`Requeued for ${describeInZone(data.scheduled_at, job.timezone)}.`);
      await refresh();
    });
  }

  async function copy(job: Job) {
    await run(async () => {
      const jobZone = job.timezone || zone;
      const at = zonedWallToUtc(copyWhen, jobZone);
      if (!at) throw new Error(`Choose a valid time in ${jobZone}.`);
      if (!window.confirm(`Queue a new copy of this post to ${job.chat_id} at ${describeInZone(at.iso, jobZone)}? The original is not affected.`))
        return;
      const response = await fetch("/api/schedules/duplicate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: job.id, schedule_at: at.iso }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok)
        throw new Error(data.error || "Copy unconfirmed; refresh.");
      say(`Copy queued for ${describeInZone(data.scheduled_at, jobZone)}.`);
      setCopyFor("");
      await refresh();
    });
  }

  const counts = jobs.reduce<Record<string, number>>((total, job) => {
    total[job.status] = (total[job.status] ?? 0) + 1;
    return total;
  }, {});
  const ordered = [...jobs].sort((left, right) => {
    const rank = (job: Job) => (job.status === "pending" ? 0 : job.status === "sending" ? 1 : 2);
    const difference = rank(left) - rank(right);
    if (difference) return difference;
    if (rank(left) === 0) return Date.parse(left.scheduled_at) - Date.parse(right.scheduled_at);
    return Date.parse(right.scheduled_at) - Date.parse(left.scheduled_at);
  });
  const late = (job: Job) => job.status === "pending" && Date.parse(job.scheduled_at) < Date.now();
  const ready =
    !disabled &&
    !busy &&
    Boolean(date) &&
    Boolean(instant) &&
    reviewed &&
    Boolean(chatId.trim()) &&
    !hasLocalImage &&
    Boolean(text.trim() || mediaUrl);

  return (
    <section className="ios-card space-y-4 p-4" aria-busy={busy}>
      <div>
        <h2 className="ios-section-title">Scheduled publishing</h2>
        <p className="ios-caption mt-1">
          Times are chosen in the timezone below and saved in UTC. A repeating post keeps its
          local wall clock, so 09:00 stays 09:00 across a daylight-saving change. Due posts
          dispatch about once a minute while the bot runs; jobs over 24 hours late are marked
          missed.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <label className="block text-xs">
          Scheduled time
          <input
            aria-label="Scheduled time"
            type="datetime-local"
            className="ios-input mt-2"
            value={date}
            disabled={busy || disabled}
            onChange={(event) => setDate(event.target.value)}
          />
        </label>
        <label className="block min-w-0 text-xs">
          Timezone
          <select
            aria-label="Timezone"
            className="ios-input mt-2"
            value={zone}
            disabled={busy || disabled}
            onChange={(event) => setZone(event.target.value)}
          >
            {zones.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-xs">
          Repeat
          <select
            aria-label="Repeat"
            className="ios-input mt-2"
            value={repeat}
            disabled={busy || disabled}
            onChange={(event) => setRepeat(event.target.value as Repeat)}
          >
            <option value="once">Once</option>
            <option value="daily">Every day</option>
            <option value="weekly">Every week</option>
          </select>
        </label>
      </div>

      {date && (
        <p className="ios-caption" role="status">
          {repeats ? "Next run" : "Sends"}:{" "}
          {instant ? describeInZone(instant.iso, zone) : "invalid time"} · {zone}
          {repeats ? ` · then keeps ${wallClock} local time` : ""}
          {repeats && preview ? ` · following run ${describeInZone(preview.iso, zone)}` : ""}
        </p>
      )}
      {instant?.shifted && (
        <p className="text-xs leading-5 text-amber-200">
          {wallClock} does not exist on that date in {zone} (daylight saving starts). The
          first valid minute is used for this occurrence only; the series keeps {wallClock}.
        </p>
      )}
      {date && !instant && (
        <p className="text-xs text-amber-200" role="alert">
          That time cannot be read in {zone}. Choose another date or timezone.
        </p>
      )}
      {hasLocalImage && (
        <p className="ios-caption">
          Use a persistent HTTPS image URL for scheduling; local image uploads cannot be scheduled.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          disabled={!ready}
          className="ios-btn ios-btn-primary text-xs"
          onClick={() => void run(schedule)}
        >
          Schedule reviewed post
        </button>
        <button
          disabled={busy || disabled}
          className="ios-btn ios-btn-glass text-xs"
          onClick={() => void run(refresh)}
        >
          Refresh scheduled posts
        </button>
      </div>

      <p className="ios-caption">
        A Telegram rate limit is retried automatically and shows as Queued with the interval it
        is waiting for. Any other failure is final and waits for you — a duplicate post is worse
        than a missing one. Editing the studio does not change an already scheduled snapshot. A
        finished post can be copied as a new post at a time you choose; the original is never
        resent. A repeating post keeps its own place in the queue: after each delivery it moves
        itself forward, and cancelling it stops the series. Pause holds a series where it stands;
        resuming skips whatever was missed instead of posting the backlog; skipping moves one
        occurrence forward. One failure stops a series and waits for you, and a series that falls
        more than a day behind skips the missed copies instead of sending them late.
      </p>

      {!loaded && <LoadingState label="Reading the scheduled queue" rows={3} />}
      {loaded && !ordered.length && (
        <EmptyState
          compact
          icon={<CalendarClock size={20} />}
          title="Nothing scheduled"
          hint="Choose a time, review the post, then schedule it. Finished jobs stay here long enough to copy or retry."
        />
      )}
      {jobs.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(counts).map(([status, value]) => (
            <span
              key={status}
              data-tone={
                status === "sent"
                  ? "good"
                  : status === "failed"
                    ? "bad"
                    : status === "unconfirmed" || status === "missed"
                      ? "warn"
                      : "neutral"
              }
              className="ios-pill text-[10px]"
            >
              {STATUS_COPY[status] ?? status} · {value}
            </span>
          ))}
        </div>
      )}
      {notice && (
        <Callout tone={noticeOk ? "success" : "warn"} live className="text-xs">
          {notice}
        </Callout>
      )}

      {ordered.map((job) => {
        const jobZone = job.timezone || undefined;
        const repeatsJob = Boolean(job.repeat && REPEAT_COPY[job.repeat]);
        return (
          <div key={job.id} className="space-y-2 rounded-xl bg-white/[0.035] p-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-sm">
                {STATUS_COPY[job.status] ?? job.status} · {job.chat_id}
              </p>
              <span className="flex flex-wrap items-center gap-1.5">
                {job.repeat && (
                  <span className="ios-pill text-[10px]" data-tone="good">
                    {REPEAT_COPY[job.repeat] ?? job.repeat}
                  </span>
                )}
                {job.paused && (
                  <span className="ios-pill text-[10px]" data-tone="warn" title="Nothing sends until resumed">
                    Paused
                  </span>
                )}
                {job.dst_adjusted && (
                  <span
                    className="ios-pill text-[10px]"
                    data-tone="warn"
                    title="This occurrence moved out of a daylight-saving gap"
                  >
                    DST-adjusted
                  </span>
                )}
                {job.attempts ? (
                  <span className="ios-pill text-[10px]" data-tone="warn">
                    auto-retry {job.attempts}
                  </span>
                ) : null}
                {late(job) && !job.paused && (
                  <span className="ios-pill text-[10px]" data-tone="warn">
                    due now
                  </span>
                )}
              </span>
            </div>
            <p className="ios-caption">
              {describeInZone(job.scheduled_at, jobZone)}
              {jobZone ? ` · ${jobZone}` : " · device time"} · {job.id}
              {job.attempts
                ? ` · ${job.attempts} automatic ${job.attempts === 1 ? "retry" : "retries"}`
                : ""}
              {job.finished_at ? ` · finished ${describeInZone(job.finished_at, jobZone)}` : ""}
              {job.sent_count
                ? ` · delivered ${job.sent_count} ${job.sent_count === 1 ? "time" : "times"}`
                : ""}
              {job.skipped ? ` · ${job.skipped} skipped while offline` : ""}
            </p>
            {job.error && (
              <Callout tone="warn" className="text-xs">
                {job.error}
              </Callout>
            )}
            {STATUS_HELP[job.status] && <p className="ios-caption">{STATUS_HELP[job.status]}</p>}
            <p className="truncate text-xs">{job.text.replace(/<[^>]+>/g, "")}</p>
            <div className="flex flex-wrap gap-2">
              {job.status === "pending" && (
                <button className="ios-btn ios-btn-glass text-xs" disabled={busy || disabled} onClick={() => void cancel(job)}>
                  Cancel scheduled post
                </button>
              )}
              {repeatsJob && job.status === "pending" && (
                <>
                  <button
                    className="ios-btn ios-btn-glass text-xs"
                    disabled={busy || disabled}
                    onClick={() => void series(job, job.paused ? "resume" : "pause")}
                  >
                    {job.paused ? <Play size={14} aria-hidden /> : <Pause size={14} aria-hidden />}
                    {job.paused ? "Resume series" : "Pause series"}
                  </button>
                  {!job.paused && (
                    <button
                      className="ios-btn ios-btn-glass text-xs"
                      disabled={busy || disabled}
                      onClick={() => void series(job, "skip")}
                    >
                      <SkipForward size={14} aria-hidden /> Skip next
                    </button>
                  )}
                </>
              )}
              {job.status !== "pending" && job.status !== "sending" && (
                <button
                  className="ios-btn ios-btn-glass text-xs"
                  disabled={busy || disabled}
                  onClick={() => {
                    const jobZone = job.timezone || zone;
                    setCopyFor(job.id);
                    setCopyWhen(wallInputOf(new Date(Date.now() + 3_600_000).toISOString(), jobZone));
                  }}
                >
                  Send a new copy
                </button>
              )}
              {job.status === "failed" && (
                <button className="ios-btn ios-btn-glass text-xs" disabled={busy || disabled} onClick={() => void retry(job)}>
                  Retry rejected post
                </button>
              )}
            </div>
            {copyFor === job.id && (
              <div className="flex flex-wrap items-end gap-2 rounded-xl border border-white/10 p-2">
                <label className="text-[11px]">
                  Copy time ({job.timezone || zone})
                  <input
                    aria-label="Copy time"
                    type="datetime-local"
                    className="ios-input mt-1"
                    value={copyWhen}
                    disabled={busy || disabled}
                    onChange={(event) => setCopyWhen(event.target.value)}
                  />
                </label>
                <button
                  className="ios-btn ios-btn-glass text-xs"
                  disabled={busy || disabled || !copyWhen}
                  onClick={() => void copy(job)}
                >
                  Queue copy
                </button>
                <button className="ios-btn ios-btn-glass text-xs" disabled={busy} onClick={() => setCopyFor("")}>
                  Dismiss
                </button>
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}
