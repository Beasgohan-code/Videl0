import { supabase } from "@/lib/supabase";
export async function GET(){
  if(!supabase) return Response.json({items:[]});
  const { data } = await supabase.from("videl_music_queue").select("*").order("position").limit(50);
  return Response.json({ items: data || [] });
}
