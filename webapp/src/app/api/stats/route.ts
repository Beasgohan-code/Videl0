import { supabase } from "@/lib/supabase";

export async function GET() {
  if (!supabase) return Response.json({ users:0, chats:0, commands:0, note:"supabase not configured" });
  try {
    const [u,c,s] = await Promise.all([
      supabase.from("videl_users").select("id", { count:"exact", head:true }),
      supabase.from("videl_chats").select("id", { count:"exact", head:true }),
      supabase.from("videl_stats").select("id", { count:"exact", head:true }),
    ]);
    return Response.json({ stats: { users: u.count ?? 0, chats: c.count ?? 0, commands: s.count ?? 0 } });
  } catch (e:any) {
    return Response.json({ error: String(e), users:0, chats:0, commands:0 }, { status: 500 });
  }
}
