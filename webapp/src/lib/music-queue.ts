export function moveQueuedTrack<T>(tracks: T[], from: number, to: number): T[] {
  if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < 0 ||
      from >= tracks.length || to >= tracks.length || from === to) {
    return tracks;
  }
  const next = [...tracks];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}
