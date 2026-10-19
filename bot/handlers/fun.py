"""
Videl0 • Fun — Cyber Dark Perfected
◍ 8ball ⫶ dice ⫶ flip ⫶ ship ⫶ meme ⫶ quote
"""
import random
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from bot.rich_ui import rich_heading, rich_note, rich_esc, rich_kv_table
from bot.utils.fonts import sc, sb

router = Router()

BALL = [sc("it is certain"), sc("without a doubt"), sc("yes definitely"), sc("ask again later"), sc("cannot predict now"), sc("don't count on it"), sc("outlook not so good"), sc("signs point to yes")]
JOKES = [sc("why did the scarecrow win? he was outstanding in his field!"), sc("parallel lines have so much in common... it's a shame they'll never meet.")]
QUOTES = [sc("be yourself; everyone else is already taken. — wilde"), sc("the only way to do great work is to love what you do. — jobs")]
TRUTHS=[sc("what's your biggest fear?"), sc("have you ever lied to your best friend?")]
DARES=[sc("do 10 pushups"), sc("send a voice note singing")]

@router.message(Command("8ball"))
async def eight_ball(m: Message):
    q=(m.text.split(maxsplit=1)[1] if len(m.text.split(maxsplit=1))>1 else "")
    if not q: return await m.reply(f"◍ {sc('usage')}: /8ball <{sc('question')}> ◍")
    await m.answer(rich_heading(f"◍ {sc('8ball')} ◍", level=3)+rich_kv_table([(sc("q"), rich_esc(q)),(sc("a"), f"<i>{random.choice(BALL)}</i>")]))

@router.message(Command("dice","roll"))
async def dice_cmd(m: Message):
    await m.answer_dice()

@router.message(Command("flip","coin"))
async def flip_cmd(m: Message):
    res=random.choice([sc("heads"), sc("tails")])
    await m.answer(f"◍ <b>{res}</b> ◍")

@router.message(Command("ship"))
async def ship_cmd(m: Message):
    if not m.reply_to_message or not m.reply_to_message.from_user: return await m.reply(f"◍ {sc('reply to someone to ship')} ◍")
    pct=random.randint(10,100)
    heart="◍" if pct>70 else "◎"
    await m.answer(rich_heading(f"⬪ {sc('ship')} ⬪", level=3)+rich_note(f"{m.from_user.full_name} {heart} {m.reply_to_message.from_user.full_name}<br>{sc('love')}: <code>{pct}%</code>"))

@router.message(Command("joke"))
async def joke_cmd(m: Message):
    await m.answer(f"⫶ {random.choice(JOKES)} ⫶")

@router.message(Command("meme"))
async def meme_cmd(m: Message):
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            async with s.get("https://meme-api.com/gimme") as r:
                j=await r.json()
                await m.bot.send_photo(m.chat.id, j["url"], caption=f"◍ {sc(j.get('title','meme').lower())} ◍")
                return
    except: pass
    await m.answer(f"◍ {sc('meme')} ◍ ⫶ https://i.imgflip.com/30b1gx.jpg")

@router.message(Command("quote"))
async def quote_cmd(m: Message):
    await m.answer(f"◎ <i>{random.choice(QUOTES)}</i> ◎")

@router.message(Command("truth"))
async def truth_cmd(m: Message): await m.answer(f"◍ {sc('truth')}: {random.choice(TRUTHS)} ◍")
@router.message(Command("dare"))
async def dare_cmd(m: Message): await m.answer(f"⬪ {sc('dare')}: {random.choice(DARES)} ⬪")
@router.message(Command("roast"))
async def roast_cmd(m: Message):
    target=m.reply_to_message.from_user.full_name if m.reply_to_message and m.reply_to_message.from_user else sc("you")
    roasts=[f"{target} — {sc('so slow, turtles look fast')}", f"{target} — {sc('id rather not roast, weak signal')}"]
    await m.answer(f"⫶ {random.choice(roasts)} ⫶")
