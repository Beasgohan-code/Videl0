# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Fun • Cyber Dark Perfected
# --------------------------------------------------------------------------------
import random
from pyrogram import filters
from pyrogram.types import Message
from videl import bot, LOGGER
from videl.utils.formatters import sc

BALL=[sc("it is certain"), sc("without a doubt"), sc("yes definitely"), sc("you may rely on it"),
      sc("outlook good"), sc("reply hazy — try again"), sc("ask again later"), sc("cannot predict now"),
      sc("don't count on it"), sc("my sources say no")]
JOKES=[sc("why did the scarecrow win? outstanding in his field."),
       sc("parallel lines have so much in common — they never meet."),
       sc("i told a joke about queue — it never ends."),
       sc("why do bots love music? great bytes.")]
QUOTES=[sc("be yourself; everyone else is already taken — wilde"),
        sc("opportunity lies in difficulty — einstein"),
        sc("stay hungry, stay foolish — jobs"),
        sc("perfect is not done, it's relentless — videl")]

@bot.on_message(filters.command(["8ball"]) & ~filters.forwarded)
async def ball_handler(_, m: Message):
    q=" ".join(m.command[1:]) if len(m.command)>1 else ""
    if not q: return await m.reply_text(f"◍ /8ball <{sc('question')}> ◍")
    await m.reply_text(f"◍ {sc('8ball')} ◍\n⫶ {sc('q')}: <code>{q}</code>\n⬪ {sc('a')}: <i>{random.choice(BALL)}</i> ⬪")

@bot.on_message(filters.command(["joke"]) & ~filters.forwarded)
async def joke_handler(_, m: Message):
    await m.reply_text(f"◍ {sc('joke')} ◍\n⫶ {random.choice(JOKES)} ⫶")

@bot.on_message(filters.command(["quote"]) & ~filters.forwarded)
async def quote_handler(_, m: Message):
    await m.reply_text(f"◎ <i>{random.choice(QUOTES)}</i> ◎\n◍ {sc('— videl')} ◍")

@bot.on_message(filters.command(["ship"]) & ~filters.forwarded)
async def ship_handler(_, m: Message):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await m.reply_text(f"◍ {sc('reply to a user to ship')} ◍")
    import html as _h
    u1=_h.escape(m.from_user.first_name or "you"); u2=_h.escape(m.reply_to_message.from_user.first_name or "them")
    pct=random.randint(10,100)
    bar="█"* (pct//10) + "░"*(10-pct//10)
    await m.reply_text(f"⬪ {sc('ship')} ⬪\n{u1} ◍ {u2}\n<code>{bar}</code> <code>{pct}%</code>\n⫶ {sc('made for each other' if pct>70 else 'keep trying')} ⫶")

@bot.on_message(filters.command(["dice","throw","roll"]) & ~filters.forwarded)
async def dice_handler(_, m: Message):
    await m.reply_dice(emoji=random.choice(["🎲","🎯","🎳","🏀","⚽"]))

@bot.on_message(filters.command(["flip","coin"]) & ~filters.forwarded)
async def flip_handler(_, m: Message):
    await m.reply_text(f"◍ {random.choice([sc('heads'), sc('tails')])} ◍")

LOGGER.info("◍ ғᴜɴ — ᴘᴇʀғᴇᴄᴛ ⬪")
