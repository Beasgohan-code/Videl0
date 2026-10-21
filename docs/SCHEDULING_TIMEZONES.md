# Repeating posts and the wall clock

A scheduled post stores an **instant** (`due_at`, UTC) and, when it repeats, an
**intended local wall clock** (`repeat_anchor`, naive local time plus the IANA
`timezone`). The instant is what the dispatcher compares with its clock; the
anchor is what the owner actually chose.

```
timezone:      Asia/Kolkata
repeat_anchor: 2026-10-21T09:00:00     # 09:00, every day
due_at:        2026-10-21T03:30:00Z    # the same moment, in UTC
```

On each accepted delivery the series adds one day (or seven) to the **anchor**,
then maps that wall clock back to an instant. That is why 09:00 survives a
daylight-saving change: the anchor never moves, only the UTC offset does.

## The two days the wall clock is not a function of UTC

| Case | Rule | Visible result |
| --- | --- | --- |
| Normal day | Wall clock → one instant | No adjustment |
| Spring-forward gap (`02:30` does not exist) | Use the first minute that exists, **for that occurrence only** | `dst_adjusted: true`, panel badge, next day back at `02:30` |
| Autumn overlap (`01:30` happens twice) | First occurrence (`fold = 0`), one send | Sent once; the second `01:30` is never a second post |

The anchor is stored separately from the first run so that a gap on day one
does not permanently drag the series to `03:00`.

## Controls

- **Pause** — the dispatcher skips paused rows, the >24 h "missed" sweep skips
  them, and the >1 day "skip ahead" sweep skips them. A paused series is
  neither sent nor declared missed.
- **Resume** — if the stored occurrence is in the past, it walks the same
  anchor forward until it is strictly in the future and counts what it passed
  in `skipped`. It never replays the pause as a burst.
- **Skip next** — moves the pending occurrence exactly one step and increments
  `skipped`. Refused while paused, for a non-repeating post, or when the
  dispatcher has already claimed the row (the update is guarded by
  `status: pending` and the exact `due_at`).

## Deliberate limits

- **The zone cannot be changed after the series exists.** Keeping the wall
  clock and keeping the instant are both defensible answers to a zone change,
  and guessing which the owner meant is worse than asking them to create a new
  series.
- **Daylight rules come from the host's tzdata.** A country that changes its
  rules updates the OS package, not this database; future occurrences move
  accordingly. Two hosts with different tzdata versions can disagree, so the
  queue should run in one place.
- **Exactly-once is best effort.** If Telegram accepts a post and the process
  dies before the database records it, the row becomes `unconfirmed` and is
  never resent automatically. A duplicate post is worse than a missing one.
- **Wall clock vs device clock.** The panel sends the instant it computed from
  the chosen zone and also sends the wall clock (`wall_time`); the backend
  refuses the pair if they disagree by more than three hours, which catches a
  client that mixed zones without blocking a legitimate gap shift.
- **One occurrence, one worker.** The claim is a single atomic
  `find_one_and_update`; running two dispatchers against the same database is
  tolerated (one wins the row) but not required or recommended.

## API

`POST /internal/scheduled-posts` (owner-only, proxied by the panel):

```json
{
  "chat_id": "-1001", "text": "<b>Hello</b>", "parse_mode": "HTML",
  "schedule_at": "2026-10-21T03:30:00Z", "request_id": "<uuid>",
  "repeat": "daily", "timezone": "Asia/Kolkata", "wall_time": "09:00"
}
```

`POST /internal/scheduled-posts/series` with `{ "id": "<uuid>", "action": "pause" | "resume" | "skip" }`.

Both refuse a stale transition with **409** and an explanation rather than
performing a best-effort guess.
