# --------------------------------------------------------------------------------
#  Videl © 2026 | Fun • Cyber Dark Perfected
# --------------------------------------------------------------------------------
import random
from pyrogram import filters
from pyrogram.types import Message
from videl import bot, LOGGER
from videl.utils.formatters import sc

BALL=[sc("it is certain"), sc("without a doubt"), sc("yes definitely"), sc("ask again later"), sc("cannot predict now")]
JOKES=[sc("why did scarecrow win? outstanding field"), sc("parallel lines have so much in common — never meet")]
QUOTES=[sc("be yourself; everyone else is already taken — wilde"), sc("opportunity in difficulty — einstein")]

@bot.on_message(filters.command(["8ball"]) & ~filters.forwarded)
async def ball_handler(_, m: Message):
    q=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not q: return await m.reply_text(f"◍ /8ball <{sc('question')}> ◍")
    await m.reply_text(f"◍ {sc('8ball')} ◍\n⫶ {sc('q')}: <code>{q}</code>\n⬪ {sc('a')}: <i>{random.choice(BALL)}</i> ⬪")

@bot.on_message(filters.command(["joke"]) & ~filters.forwarded)
async def joke_handler(_, m: Message): await m.reply_text(f"⫶ {random.choice(JOKES)} ⫶")

@bot.on_message(filters.command(["quote"]) & ~filters.forwarded)
async def quote_handler(_, m: Message): await m.reply_text(f"◎ <i>{random.choice(QUOTES)}</i> ◎")

@bot.on_message(filters.command(["ship"]) & ~filters.forwarded)
async def ship_handler(_, m: Message):
    if not m.reply_to_message or not m.reply_to_message.from_user: return await m.reply_text(f"◍ {sc('reply to ship')} ◍")
    pct=random.randint(10,100)
    await m.reply_text(f"⬪ {sc('ship')} ⬪\n{m.from_user.first_name} ◍ {m.reply_to_message.from_user.first_name}\n{sc('love')}: <code>{pct}%</code>")

LOGGER.info("✅ Fun module loaded")
