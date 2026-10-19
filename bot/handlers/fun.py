"""
Videl0 • Fun — 8ball, dice, flip, ship, joke, meme, quote, truth/dare, roast
"""
import random
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from bot.rich_ui import rich_heading, rich_note, rich_esc, rich_kv_table

router = Router()

BALL = ["It is certain","Without a doubt","Yes — definitely","Ask again later","Cannot predict now","Don't count on it","My sources say no","Outlook not so good","Signs point to yes","Very doubtful"]
JOKES = ["Why did the scarecrow win an award? He was outstanding in his field!","I told my wife she was drawing eyebrows too high. She looked surprised.","Parallel lines have so much in common… it's a shame they'll never meet."]
QUOTES = ["Be yourself; everyone else is already taken. — Wilde","The only way to do great work is to love what you do. — Jobs","In the middle of difficulty lies opportunity. — Einstein"]
TRUTHS=["What's your biggest fear?","Have you ever lied to your best friend?","What is your most embarrassing moment?"]
DARES=["Do 10 pushups","Send a voice note singing","Text your crush 'hi'"]

@router.message(Command("8ball"))
async def eight_ball(m: Message):
    q=(m.text.split(maxsplit=1)[1] if len(m.text.split(maxsplit=1))>1 else "")
    if not q: return await m.reply("Usage: /8ball <question>")
    await m.answer(rich_heading("🎱 8Ball", level=3)+rich_kv_table([("Q", rich_esc(q)),("A", f"<i>{random.choice(BALL)}</i>")]))

@router.message(Command("dice","roll"))
async def dice_cmd(m: Message):
    await m.answer_dice()

@router.message(Command("flip","coin"))
async def flip_cmd(m: Message):
    await m.answer(f"🪙 **{random.choice(['Heads','Tails'])}**")

@router.message(Command("ship"))
async def ship_cmd(m: Message):
    if not m.reply_to_message or not m.reply_to_message.from_user: return await m.reply("Reply to someone to ship!")
    pct=random.randint(10,100)
    await m.answer(rich_heading("💘 Ship", level=3)+rich_note(f"{m.from_user.full_name} ❤️ {m.reply_to_message.from_user.full_name}<br>Love: <code>{pct}%</code> {'💖' if pct>70 else '💔'}"))

@router.message(Command("joke"))
async def joke_cmd(m: Message):
    await m.answer(f"😂 {random.choice(JOKES)}")

@router.message(Command("meme"))
async def meme_cmd(m: Message):
    # use meme-api
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            async with s.get("https://meme-api.com/gimme") as r:
                j=await r.json()
                await m.bot.send_photo(m.chat.id, j["url"], caption=j.get("title",""))
                return
    except: pass
    await m.answer("😂 Meme: https://i.imgflip.com/30b1gx.jpg")

@router.message(Command("quote"))
async def quote_cmd(m: Message):
    await m.answer(f"💭 <i>{random.choice(QUOTES)}</i>")

@router.message(Command("truth"))
async def truth_cmd(m: Message): await m.answer(f"🤔 Truth: {random.choice(TRUTHS)}")
@router.message(Command("dare"))
async def dare_cmd(m: Message): await m.answer(f"😈 Dare: {random.choice(DARES)}")
@router.message(Command("roast"))
async def roast_cmd(m: Message):
    target=m.reply_to_message.from_user.full_name if m.reply_to_message and m.reply_to_message.from_user else "you"
    roasts=[f"{target}, you're so slow, you make turtles look like race cars.","{target}, I'd roast you but my mom said not to bully the weak."]
    await m.answer(random.choice(roasts))
