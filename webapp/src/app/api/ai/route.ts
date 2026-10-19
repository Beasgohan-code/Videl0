export async function POST(req: Request){
  const { prompt } = await req.json().catch(()=>({prompt:""}));
  if(!prompt) return Response.json({ error:"no prompt" }, { status:400 });
  // call same provider as bot: prefer Groq/OpenAI via env? proxy
  // For demo, return echo if no key configured.
  const key = process.env.OPENAI_API_KEY || process.env.GROQ_API_KEY;
  if(!key) return Response.json({ answer: `[Videl AI] You said: ${prompt} (add OPENAI_API_KEY to enable real AI)` });
  try {
    if(process.env.OPENAI_API_KEY){
      const r=await fetch("https://api.openai.com/v1/chat/completions",{
        method:"POST",
        headers:{"Authorization":`Bearer ${process.env.OPENAI_API_KEY}`,"Content-Type":"application/json"},
        body: JSON.stringify({ model:"gpt-4o-mini", messages:[{role:"user", content: prompt}], max_tokens: 600 })
      });
      const j=await r.json();
      const ans=j.choices?.[0]?.message?.content || JSON.stringify(j);
      return Response.json({ answer: ans });
    }
    if(process.env.GROQ_API_KEY){
      const r=await fetch("https://api.groq.com/openai/v1/chat/completions",{
        method:"POST",
        headers:{"Authorization":`Bearer ${process.env.GROQ_API_KEY}`,"Content-Type":"application/json"},
        body: JSON.stringify({ model:"llama-3.1-8b-instant", messages:[{role:"user", content: prompt}] })
      });
      const j=await r.json();
      return Response.json({ answer: j.choices?.[0]?.message?.content || "..." });
    }
  } catch(e:any){
    return Response.json({ error: String(e) }, { status:500 });
  }
  return Response.json({ answer: "No AI configured" });
}
