import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { InviteRoom } from "@/components/arcade/InviteRoom";

/**
 * /play/CODE — the invite as a real address.
 *
 * Deliberately its own route instead of a panel tab: a link pasted into a
 * group chat has to open in whatever browser the reader has, and the code has
 * to be readable before any script runs, so it also travels in the preview.
 */
const CODE = /^[A-Z2-9]{4,8}$/;

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const code = String((await params).code || "").toUpperCase();
  if (!CODE.test(code)) return { title: "Videl Arcade" };
  return {
    title: `${code} · a table is waiting — Videl Arcade`,
    description: `You have been invited to table ${code}. Multiplayer Ludo, Checkers, Connect Four, Reversi and Tic-tac-toe.`,
    openGraph: {
      title: `Take a chair — table ${code}`,
      description: "Multiplayer board games on Videl. The board lives on the server.",
    },
  };
}

export default async function PlayPage({ params }: { params: Promise<{ code: string }> }) {
  const code = String((await params).code || "").toUpperCase();
  if (!CODE.test(code)) notFound();
  return <InviteRoom code={code} />;
}
