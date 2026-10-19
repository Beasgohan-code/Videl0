"""
Videl0 • AI Provider — multi-backend fallback
OpenAI → Groq → Gemini → Mistral → local echo
"""
import logging
from bot.config import OPENAI_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY, AI_SYSTEM_PROMPT, AI_DEFAULT_MODEL, AI_MAX_TOKENS
log=logging.getLogger("videl.ai")

SYSTEM=AI_SYSTEM_PROMPT

async def ask_ai(prompt: str, history: list[dict] | None = None, model: str | None = None, system: str | None = None, image_url: str|None=None) -> str:
    """
    history: [{role, content}]
    Returns text.
    """
    model = model or AI_DEFAULT_MODEL
    sys_prompt = system or SYSTEM
    messages=[{"role":"system","content":sys_prompt}]
    if history:
        for h in history[-10:]:
            messages.append({"role":h.get("role","user"),"content":h.get("content","")})
    # handle image for vision
    if image_url:
        messages.append({"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":image_url}}]})
    else:
        messages.append({"role":"user","content":prompt})

    # 1. OpenAI
    if OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI
            client=AsyncOpenAI(api_key=OPENAI_API_KEY)
            resp=await client.chat.completions.create(model=model if "gpt" in model else "gpt-4o-mini",
                                                      messages=messages, max_tokens=AI_MAX_TOKENS, temperature=0.7)
            return resp.choices[0].message.content
        except Exception as e: log.warning(f"OpenAI fail: {e}")

    # 2. Groq
    if GROQ_API_KEY:
        try:
            from groq import AsyncGroq
            client=AsyncGroq(api_key=GROQ_API_KEY)
            gmodel="llama-3.1-8b-instant" if "gpt" in model else model
            if "llama" not in gmodel and "mixtral" not in gmodel: gmodel="llama-3.1-8b-instant"
            resp=await client.chat.completions.create(model=gmodel, messages=messages, max_tokens=AI_MAX_TOKENS, temperature=0.7)
            return resp.choices[0].message.content
        except Exception as e: log.warning(f"Groq fail: {e}")

    # 3. Gemini
    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            m=genai.GenerativeModel("gemini-1.5-flash")
            # join messages to prompt
            joined="\n".join(f"{mm['role']}: {mm['content']}" for mm in messages)
            r=m.generate_content(joined)
            return r.text
        except Exception as e: log.warning(f"Gemini fail: {e}")

    # 4. Mistral
    if MISTRAL_API_KEY:
        try:
            from mistralai.async_client import MistralAsyncClient
            client=MistralAsyncClient(api_key=MISTRAL_API_KEY)
            from mistralai.models.chat_completion import ChatMessage
            mc=[ChatMessage(role=mm["role"], content=mm["content"] if isinstance(mm["content"],str) else str(mm["content"])) for mm in messages]
            resp=await client.chat(model="mistral-small", messages=mc)
            return resp.choices[0].message.content
        except Exception as e: log.warning(f"Mistral fail: {e}")

    return "🤖 AI is not configured. Add OPENAI_API_KEY / GROQ_API_KEY / GEMINI_API_KEY to .env"

async def generate_image(prompt: str, model: str="dall-e-3") -> str | None:
    """Returns image URL if available."""
    if OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI
            client=AsyncOpenAI(api_key=OPENAI_API_KEY)
            r=await client.images.generate(model="dall-e-3", prompt=prompt, n=1, size="1024x1024")
            return r.data[0].url
        except Exception as e: log.warning(f"img gen fail: {e}")
    # pollinations fallback (free)
    try:
        import urllib.parse
        q=urllib.parse.quote(prompt)
        return f"https://image.pollinations.ai/prompt/{q}?model=turbo&nologo=true"
    except: return None

async def summarize_text(text: str) -> str:
    return await ask_ai(f"Summarize concisely in bullet points:\n\n{text[:4000]}", system="You are a summarizer. Be crisp.")

async def translate_text(text: str, target: str="en") -> str:
    return await ask_ai(f"Translate to {target}, keep formatting:\n\n{text}", system="You are a translator.")
