import { redirect } from "next/navigation";

/** /play on its own is not a room; send people to the lobby that lists them. */
export default function PlayIndex() {
  redirect("/?tab=arcade");
}
