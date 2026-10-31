"use client";
import { useCallback, useEffect, useState } from "react";
import { CalendarDays, Check, ChevronRight, Clock3, Gamepad2, Music2, Users } from "lucide-react";
import { useStudio } from "@/components/studio/StudioProvider";
import { Callout } from "./ui";

type EventRow = {
  id: string; title: string; description: string; chat_id: string | number; chat_title: string;
  starts_at: string; creator: string; music_query: string; game_room: string;
  status?: "upcoming" | "cancelled";
  rsvp_counts: { going: number; maybe: number; not_going: number };
  my_rsvp: "going" | "maybe" | "not_going" | null;
  attendees: { name: string; status: string }[];
  announcement_sent?: boolean;
  cancellation_sent?: boolean;
  update_notice_sent?: boolean;
  can_manage?: boolean;
};
type GroupRow = { id: number; title: string; type?: string };

function localDate(hours = 24) {
  const date = new Date(Date.now() + hours * 60 * 60 * 1000);
  date.setMinutes(Math.ceil(date.getMinutes() / 15) * 15, 0, 0);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function when(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZoneName: "short" }).format(new Date(value));
}

function calendarEscape(value: string) {
  return value.replace(/\\/g, "\\\\").replace(/\r?\n/g, "\\n").replace(/,/g, "\\,").replace(/;/g, "\\;");
}

function downloadCalendar(event: EventRow) {
  const start = new Date(event.starts_at);
  const end = new Date(start.getTime() + 60 * 60 * 1000);
  const stamp = (date: Date) => date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  const invite = new URL(window.location.href); invite.searchParams.set("event", event.id);
  const lines = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Videl//Event Room//EN", "CALSCALE:GREGORIAN", "BEGIN:VEVENT",
    `UID:${event.id}@videl.studio`, `DTSTAMP:${stamp(new Date())}`, `DTSTART:${stamp(start)}`, `DTEND:${stamp(end)}`,
    `SUMMARY:${calendarEscape(event.title)}`, `DESCRIPTION:${calendarEscape([event.description, `Group: ${event.chat_title}`].filter(Boolean).join("\n"))}`,
    `URL:${invite.toString()}`, "END:VEVENT", "END:VCALENDAR",
  ];
  const url = URL.createObjectURL(new Blob([lines.join("\r\n") + "\r\n"], { type: "text/calendar;charset=utf-8" }));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${event.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "videl-event"}.ics`; anchor.click();
  URL.revokeObjectURL(url);
}

export function EventRooms({ eventId, onJoinGame }: { eventId?: string; onJoinGame: (code: string) => void }) {
  const { open } = useStudio();
  const [events, setEvents] = useState<EventRow[]>([]);
  const [groups, setGroups] = useState<GroupRow[]>([]);
  const [selected, setSelected] = useState<EventRow | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [chatId, setChatId] = useState("");
  const [startsAt, setStartsAt] = useState(localDate());
  const [music, setMusic] = useState("");
  const [gameRoom, setGameRoom] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState(false);

  const request = useCallback(async (url: string, init?: RequestInit) => {
    const response = await fetch(url, { ...init, cache: "no-store", headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.error || "Event Rooms are unavailable");
    return data;
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [eventData, groupData] = await Promise.all([
        request("/api/arcade/events"),
        request("/api/arcade/events/groups"),
      ]);
      setEvents(eventData.events || []);
      setGroups(groupData.groups || []);
      setChatId((current) => current || String(groupData.groups?.[0]?.id || ""));
      setError("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not load events");
    } finally { setLoading(false); }
  }, [request]);

  useEffect(() => { void reload(); }, [reload]);
  useEffect(() => {
    if (!eventId) { setSelected(null); return; }
    let active = true;
    request(`/api/arcade/events/${encodeURIComponent(eventId)}`).then((data) => {
      if (active) { setSelected(data.event); setError(""); }
    }).catch((failure) => {
      if (active) setError(failure instanceof Error ? failure.message : "This event link is unavailable");
    });
    return () => { active = false; };
  }, [eventId, request]);

  async function createEvent(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true); setError(""); setNotice("");
    try {
      const payload = { title, description, starts_at: new Date(startsAt).toISOString(), music_query: music, game_room: gameRoom };
      const data = editing && selected
        ? await request(`/api/arcade/events/${selected.id}`, { method: "POST", body: JSON.stringify({ action: "edit", ...payload }) })
        : await request("/api/arcade/events", { method: "POST", body: JSON.stringify({ chat_id: chatId, ...payload }) });
      const saved = data.event as EventRow;
      setEvents((rows) => [saved, ...rows.filter((row) => row.id !== saved.id)]);
      setSelected(saved);
      setEditing(false);
      if (!editing) { setTitle(""); setDescription(""); setMusic(""); setGameRoom(""); setStartsAt(localDate()); }
      setNotice(editing
        ? saved.update_notice_sent ? "Event updated and the group was notified." : "Event updated. Telegram did not confirm the group notice."
        : saved.announcement_sent ? "Event room created and announced in Telegram." : "Event room created. Telegram did not confirm the announcement; share the event link instead.");
      const url = new URL(window.location.href); url.searchParams.set("event", saved.id); window.history.replaceState(window.history.state, "", url.pathname + url.search);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Could not create the event"); }
    finally { setSaving(false); }
  }

  async function createLinkedRoom() {
    if (!chatId) return;
    setSaving(true); setError("");
    try {
      const data = await request("/api/arcade", { method: "POST", body: JSON.stringify({
        game: "chess", seats: 2, visibility: "public", chat_id: chatId, title: title || "Community event",
      }) });
      setGameRoom(data.room.code);
      setNotice(`Arcade table ${data.room.code} linked to ${groups.find((group) => String(group.id) === chatId)?.title || "your group"}.`);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Could not create the Arcade table"); }
    finally { setSaving(false); }
  }

  function editEvent() {
    if (!selected || !selected.can_manage || selected.status !== "upcoming") return;
    const date = new Date(selected.starts_at);
    setChatId(String(selected.chat_id));
    setTitle(selected.title);
    setDescription(selected.description || "");
    setMusic(selected.music_query || "");
    setGameRoom(selected.game_room || "");
    setStartsAt(new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16));
    setEditing(true);
    setNotice("Edit the details below. Videl will verify your current group-admin status before saving.");
  }

  async function cancelEvent() {
    if (!selected || !selected.can_manage || !window.confirm(`Cancel “${selected.title}” for everyone?`)) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const data = await request(`/api/arcade/events/${selected.id}`, { method: "POST", body: JSON.stringify({ action: "cancel" }) });
      setSelected(data.event);
      setEvents((rows) => rows.map((row) => row.id === data.event.id ? data.event : row));
      setNotice(data.event.cancellation_sent ? "Event cancelled and the group was notified." : "Event cancelled. Telegram did not confirm the group notice.");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Could not cancel the event"); }
    finally { setSaving(false); }
  }

  async function rsvp(status: "going" | "maybe" | "not_going") {
    if (!selected) return;
    setSaving(true); setError("");
    try {
      const data = await request(`/api/arcade/events/${selected.id}`, { method: "POST", body: JSON.stringify({ status }) });
      setSelected(data.event);
      setEvents((rows) => rows.map((row) => row.id === data.event.id ? data.event : row));
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Could not save RSVP"); }
    finally { setSaving(false); }
  }

  const share = async (row: EventRow) => {
    const url = new URL(window.location.href); url.searchParams.set("event", row.id);
    try { await navigator.clipboard.writeText(url.toString()); setNotice("Event link copied."); }
    catch { setNotice(url.toString()); }
  };

  return (
    <section className="ios-card mt-5 overflow-hidden p-5" aria-labelledby="event-rooms-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="ios-caps text-[10px] text-fuchsia-200">Plan together · show up together</p>
          <h2 id="event-rooms-title" className="mt-1 text-lg font-semibold">Event Rooms</h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-indigo-100/50">Create a group event, collect RSVPs, and give everyone one place for the plan, music and an optional Arcade table.</p>
        </div>
        <button type="button" onClick={() => void reload()} className="ios-btn ios-btn-glass text-xs"><CalendarDays size={14}/> Refresh</button>
      </div>
      {error && <Callout tone="warn" className="mt-4">{error}</Callout>}
      {notice && <p role="status" className="mt-3 break-all text-xs text-emerald-200/80">{notice}</p>}
      {selected && (
        <article className="mt-4 rounded-2xl border border-fuchsia-300/15 bg-gradient-to-br from-fuchsia-400/[0.08] to-indigo-400/[0.04] p-4">
          <div className="flex flex-wrap justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] text-fuchsia-200/70">{selected.chat_title} · hosted by {selected.creator}</p>
              <h3 className="mt-1 break-words text-xl font-semibold">{selected.title}</h3>
              <p className="mt-2 flex items-center gap-2 text-xs text-indigo-100/60"><Clock3 size={13}/>{when(selected.starts_at)}</p>
              {selected.description && <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-indigo-50/75">{selected.description}</p>}
            </div>
            <div className="flex flex-wrap gap-2 self-start">
              <button type="button" onClick={() => void share(selected)} className="ios-btn ios-btn-glass text-xs">Share invite</button>
              <button type="button" onClick={() => downloadCalendar(selected)} className="ios-btn ios-btn-glass text-xs"><CalendarDays size={13}/> Add to calendar</button>
              {selected.can_manage && selected.status === "upcoming" && <><button type="button" disabled={saving} onClick={editEvent} className="ios-btn ios-btn-glass text-xs">Edit event</button><button type="button" disabled={saving} onClick={() => void cancelEvent()} className="ios-btn ios-btn-glass text-xs text-rose-200">Cancel event</button></>}
            </div>
          </div>
          {selected.status === "cancelled" && <p className="mt-3 rounded-lg border border-rose-300/10 bg-rose-300/5 p-2 text-xs text-rose-100/80">This event was cancelled{selected.can_manage ? "." : ". The host has been notified."}</p>}
          {new Date(selected.starts_at).getTime() < Date.now() && selected.status !== "cancelled" && <p className="mt-3 rounded-lg border border-indigo-300/10 bg-indigo-300/5 p-2 text-[11px] text-indigo-100/60">RSVP snapshot: {selected.rsvp_counts.going} marked Going · this is not an attendance record.</p>}
          <div className="mt-4 flex flex-wrap gap-2">
            {(["going", "maybe", "not_going"] as const).map((status) => {
              const label = status === "going" ? `Going · ${selected.rsvp_counts.going}` : status === "maybe" ? `Maybe · ${selected.rsvp_counts.maybe}` : `Can't go · ${selected.rsvp_counts.not_going}`;
              return <button key={status} type="button" disabled={saving} onClick={() => void rsvp(status)} aria-pressed={selected.my_rsvp === status} className={`rounded-xl border px-3 py-2 text-xs ${selected.my_rsvp === status ? "border-emerald-300/30 bg-emerald-300/10 text-emerald-100" : "border-white/10 bg-white/[0.03] text-indigo-100/65"}`}>{selected.my_rsvp === status && <Check size={12} className="mr-1 inline"/>}{label}</button>;
            })}
          </div>
          {(selected.music_query || selected.game_room) && <div className="mt-4 flex flex-wrap gap-2 border-t border-white/5 pt-3">
            {selected.music_query && <button type="button" onClick={() => open("music")} className="ios-btn ios-btn-glass text-xs"><Music2 size={13}/> Music: {selected.music_query}</button>}
            {selected.game_room && <button type="button" onClick={() => onJoinGame(selected.game_room)} className="ios-btn ios-btn-glass text-xs"><Gamepad2 size={13}/> Join Arcade room {selected.game_room}</button>}
          </div>}
          {selected.attendees.length > 0 && <p className="mt-3 text-[10px] text-indigo-100/45"><Users size={12} className="mr-1 inline"/>Going: {selected.attendees.map((person) => person.name).join(", ")}</p>}
        </article>
      )}
      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,.8fr)]">
        <div>
          <h3 className="text-xs font-semibold text-indigo-50/80">Your upcoming events</h3>
          <div className="mt-2 space-y-2">
            {events.length ? events.map((row) => <button key={row.id} type="button" onClick={() => { setSelected(row); setEditing(false); const url = new URL(window.location.href); url.searchParams.set("event", row.id); window.history.replaceState(window.history.state, "", url.pathname + url.search); }} className="flex w-full items-center gap-3 rounded-xl border border-white/5 bg-white/[0.025] p-3 text-left hover:bg-white/[0.05]">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-fuchsia-300/10 text-fuchsia-200"><CalendarDays size={16}/></span>
              <span className="min-w-0 flex-1"><span className="block truncate text-xs font-medium">{row.title}</span><span className="mt-1 block truncate text-[10px] text-indigo-100/40">{row.chat_title} · {when(row.starts_at)}</span></span>
              <span className="text-[10px] text-emerald-200">{row.rsvp_counts.going} going</span><ChevronRight size={14} className="text-indigo-100/30"/>
            </button>) : <p className="rounded-xl border border-dashed border-white/10 p-4 text-xs text-indigo-100/40">{loading ? "Loading your events…" : "No upcoming events yet. Create one for a group you administer."}</p>}
          </div>
        </div>
        <form onSubmit={createEvent} className="rounded-2xl border border-white/5 bg-white/[0.025] p-4">
          <div className="flex items-center justify-between gap-2"><h3 className="text-xs font-semibold text-indigo-50/80">{editing ? "Edit event details" : "Host an event"}</h3>{editing && <button type="button" onClick={() => setEditing(false)} className="text-[10px] text-indigo-100/50 hover:text-white">Stop editing</button>}</div>
          <label className="mt-3 block text-[11px] text-indigo-100/55">Telegram group
            <select required disabled={editing} value={chatId} onChange={(event) => setChatId(event.target.value)} className="ios-input mt-1.5">
              <option value="">Choose a group you administer</option>{groups.map((group) => <option key={group.id} value={group.id}>{group.title}</option>)}
            </select>
          </label>
          {!groups.length && !loading && <p className="mt-2 text-[10px] text-amber-100/60">No admin groups found. Videl verifies your current Telegram permissions before publishing.</p>}
          <label className="mt-3 block text-[11px] text-indigo-100/55">Event name<input required minLength={3} maxLength={80} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Community game night" className="ios-input mt-1.5"/></label>
          <label className="mt-3 block text-[11px] text-indigo-100/55">Starts at<input required type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} className="ios-input mt-1.5"/></label>
          <label className="mt-3 block text-[11px] text-indigo-100/55">What should guests know?<textarea maxLength={600} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Add the plan, timezone notes, or what to bring…" className="ios-input mt-1.5 min-h-20"/></label>
          <label className="mt-3 block text-[11px] text-indigo-100/55">Optional music request<input maxLength={100} value={music} onChange={(event) => setMusic(event.target.value)} placeholder="Artist or track to queue" className="ios-input mt-1.5"/></label>
          <label className="mt-3 block text-[11px] text-indigo-100/55">Optional Arcade room code<input maxLength={8} value={gameRoom} onChange={(event) => setGameRoom(event.target.value.toUpperCase())} placeholder="Create a table in Arcade first" className="ios-input mt-1.5"/></label>
          <button type="button" disabled={saving || loading || !chatId} onClick={() => void createLinkedRoom()} className="ios-btn ios-btn-glass mt-2 w-full justify-center text-[11px]"><Gamepad2 size={13}/> Create linked public chess table</button>
          <button disabled={saving || loading || (!editing && (!groups.length || !chatId)) || (editing && !selected?.can_manage)} className="ios-btn ios-btn-primary mt-4 w-full justify-center text-xs disabled:opacity-45"><CalendarDays size={14}/>{saving ? (editing ? "Saving…" : "Creating…") : editing ? "Save & announce update" : "Create & announce event"}</button>
          <p className="mt-2 text-[10px] leading-4 text-indigo-100/35">Videl posts the invite to the selected group. Reminders are sent there before the event.</p>
        </form>
      </div>
    </section>
  );
}
