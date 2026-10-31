import { ownerRequired } from "@/lib/auth";
import { groupCall, parseChatId } from "@/lib/group-backend";
import { BACKUP_MAX_BYTES } from "@/lib/group-backup";

export const dynamic = "force-dynamic";

/** Download one group's portable configuration backup. */
export async function GET(req: Request, context: { params: Promise<{ id: string }> }) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const chatId = parseChatId((await context.params).id);
  if (chatId === null)
    return Response.json({ ok: false, error: "A group chat ID is required" }, { status: 400 });
  return groupCall(`/internal/chat/${chatId}/backup`);
}

/**
 * Preview or apply a backup, or restore the snapshot a previous import saved.
 *
 * ``dry_run`` defaults to true: a file that was made for another group must be
 * reviewed before it replaces anything.
 */
export async function POST(req: Request, context: { params: Promise<{ id: string }> }) {
  const denied = ownerRequired(req);
  if (denied) return denied;
  const chatId = parseChatId((await context.params).id);
  if (chatId === null)
    return Response.json({ ok: false, error: "A group chat ID is required" }, { status: 400 });
  if (Number(req.headers.get("content-length") || 0) > BACKUP_MAX_BYTES) {
    return Response.json({ ok: false, error: "That file is larger than a group backup can be" }, { status: 413 });
  }
  const body = await req.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return Response.json({ ok: false, error: "A backup document is required" }, { status: 400 });
  }
  const incoming = body as Record<string, unknown>;
  const payload: Record<string, unknown> = { action: "backup_import" };
  // Applying a previewed file must not silently overwrite an edit made since
  // the preview: forward the revision only when it is a sane integer.
  if (typeof incoming.revision === "number" && Number.isInteger(incoming.revision) && incoming.revision >= 0) {
    payload.revision = incoming.revision;
  }
  if (typeof incoming.backup_id === "string") {
    payload.action = "backup_restore";
    payload.backup_id = incoming.backup_id;
  } else if (incoming.document && typeof incoming.document === "object") {
    payload.document = incoming.document;
    payload.dry_run = incoming.dry_run !== false;
    if (Array.isArray(incoming.sections)) payload.sections = incoming.sections;
  } else {
    return Response.json({ ok: false, error: "Attach a backup document to import" }, { status: 400 });
  }
  return groupCall(`/internal/chat/${chatId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
