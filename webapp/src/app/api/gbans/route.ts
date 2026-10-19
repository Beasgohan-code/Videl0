import { supabase } from "@/lib/supabase";
export async function GET(){
  if(!supabase) return Response.json({items:[]});
  const { data } = await supabase.from("videl_gbans").select("*").limit(100);
  return Response.json({ items: data || [] });
}
