# --------------------------------------------------------------------------------
#  Videl © 2026 | Developed by Beasgohan-code — Premium Costume Emoji
#  User-supplied premium emoji IDs — NewsEmoji + tgiosicons + @rijif + SoLo_HaMiD
#  Telegram eligibility applies: IDs alone do not grant Premium rendering.
#  <tg-emoji emoji-id="..."> fallback uses HTML parse_mode
# --------------------------------------------------------------------------------
from __future__ import annotations
import os
import html
import re
import config

# ── Premium toggle — env USE_PREMIUM_EMOJI=1 (default ON) ─────────────────────
USE_PREMIUM: bool = os.getenv("USE_PREMIUM_EMOJI", "1").strip().lower() not in ("0","false","no","off")

# ── Existing configured IDs (validate with /emojiinfo) — 4 packs ───────────────────────
# Pack 1: https://t.me/addemoji/NewsEmoji (NewsEmoji)
# Pack 2: https://t.me/addemoji/tgiosicons (Telegram iOS Icons)
# Pack 3: https://t.me/addemoji/Udif7rr7_by_fStikBot (@rijif)
# Pack 4: https://t.me/addemoji/SoLo_HaMiD (@Boseh | @NewEmojis)
PREMIUM_IDS: dict[str, str] = {
    # ── Cyber Dark core (replaces ◍ ⬪ ⫶ ⬩ 𖦹 ⦿ ◎ ⬢ ➪) ──
    "orb":       "5042302287087666158",  # 🔮 NewsEmoji: @rijif — crystal orb for ◍
    "diamond":   "5427168083074628963",  # 💎 NewsEmoji — diamond for ⬪
    "line":      "5456140674028019486",  # ⚡️ NewsEmoji — bolt for ⫶
    "small":     "5411225014148014586",  # 🔴 NewsEmoji — red dot for ⬩
    "spark":     "5325547803936572038",  # ✨ NewsEmoji — spark for 𖦹
    "circle":    "5210956306952758910",  # 👀 NewsEmoji — eye for ⦿
    "target":    "5341715473882955310",  # ⚙️ NewsEmoji — gear for ◎
    "hex":       "5251203410396458957",  # 🛡 NewsEmoji — shield for ⬢
    "arrow":     "5416117059207572332",  # ➡️ NewsEmoji — arrow for ➪
    "dash":      "5443038326535759644",  # 💬 NewsEmoji — chat for ─

    # ── Status / moderation ──
    "check":     "5084979757905347540",  # ✅ SoLo — check
    "check2":    "5206607081334906820",  # ✔️ NewsEmoji — alt check
    "cross":     "5210952531676504517",  # ❌ NewsEmoji — cross
    "cross2":    "5040042498634810056",  # ❌ @rijif — alt cross
    "warn":      "5447644880824181073",  # ⚠️ NewsEmoji — warn
    "warn2":     "5420323339723881652",  # ⚠️ NewsEmoji — alt warn
    "ban":       "5260293700088511294",  # ⛔️ NewsEmoji — ban
    "forbid":    "5240241223632954241",  # 🚫 NewsEmoji — forbid
    "exclaim":   "5274099962655816924",  # ❗️ NewsEmoji — exclaim
    "double_ex": "5440660757194744323",  # ‼️ NewsEmoji
    "question":  "5436113877181941026",  # ❓ NewsEmoji
    "quest2":    "5452069934089641166",  # ❓ NewsEmoji alt

    # ── Locks / security ──
    "lock":      "5296369303661067030",  # 🔒 NewsEmoji
    "unlock":    "6037496202990194718",  # 🔓 tgiosicons
    "shield":    "6030445631921721471",  # 🛡 tgiosicons alt
    "key":       "5962952497197748583",  # 🔧 tgiosicons

    # ── Media / music ──
    "music":     "5463107823946717464",  # 🎵 NewsEmoji
    "music2":    "6037364759811068375",  # 🎶 tgiosicons
    "mic":       "5224736245665511429",  # 🎤 NewsEmoji
    "mic2":      "5294339927318739359",  # 🎙 NewsEmoji
    "speaker":   "5388632425314140043",  # 🔈 NewsEmoji
    "pin":       "5397782960512444700",  # 📌 NewsEmoji
    "pin2":      "4917985158784615388",  # 📌 SoLo

    # ── Arrows / nav ──
    "right":     "5416117059207572332",  # ➡️
    "left":      "5960671702059848143",  # ⬅️ tgiosicons
    "up":        "5449683594425410231",  # 🔼
    "down":      "5447183459602669338",  # 🔽
    "up2":       "5963103826075456248",  # ⬆️
    "down2":     "5963087934696459905",  # ⬇️

    # ── Info / utils ──
    "info":      "5334544901428229844",  # ℹ️ NewsEmoji
    "info2":     "5323442290708985472",  # ©
    "globe":     "5447410659077661506",  # 🌐 NewsEmoji
    "stats":     "5231200819986047254",  # 📊
    "link":      "5271604874419647061",  # 🔗 NewsEmoji
    "link2":     "6028171274939797252",  # 🔗 tgiosicons
    "search":    "5231012545799666522",  # 🔍
    "fire":      "5424972470023104089",  # 🔥
    "boom":      "5276032951342088188",  # 💥
    "star":      "5438496463044752972",  # ⭐️
    "sparkle2":  "5172834782823842584",  # ✨ SoLo
    "crown":     "5217822164362739968",  # 👑
    "diamond2":  "5409048419211682843",  # 💵
    "money":     "5402186569006210455",  # 💱

    # ── Fun / costume ──
    "eyes":      "5039623284056917259",  # 👀 @rijif
    "lightning": "5042334757040423886",  # ⚡️ @rijif
    "brain":     "5040030395416969985",  # 🧠 @rijif
    "skull":     "5042209657527993345",  # 💀 @rijif
    "ghost":     "5042097984083330584",  # 👻 @rijif
    "clown":     "5269531045165816230",  # 🤡 NewsEmoji
    "robot":     "6030400221232501136",  # 🤖 tgiosicons

    # ── Numbers (for pagination) ──
    "one":       "5141109049114232089",  # 1️⃣
    "two":       "5140871649091912628",  # 2️⃣
    "three":     "5141399818400170896",  # 3️⃣
}

# Fallback glyphs — cyber dark original
FALLBACK: dict[str, str] = {
    "orb":"🔮","diamond":"💎","line":"⚡️","small":"🔴","spark":"✨",
    "circle":"👀","target":"⚙️","hex":"🛡️","arrow":"➡️","dash":"💬",
    "check":"✅","cross":"❌","warn":"⚠️","ban":"⛔️","lock":"🔒","unlock":"🔓",
    "pin":"📌","music":"🎵","right":"➡️","left":"⬅️","up":"🔼","down":"🔽",
    "crown":"👑","shield":"🛡️","key":"🔧","stats":"📊","mic":"🎤",
    "info":"ℹ️","globe":"🌐","link":"🔗","fire":"🔥","star":"⭐️","eyes":"👀",
    "check2":"✔️","cross2":"❌","warn2":"⚠️","forbid":"🚫","exclaim":"❗️",
    "double_ex":"‼️","question":"❓","quest2":"❓","music2":"🎶",
    "mic2":"🎙️","speaker":"🔈","pin2":"📌","up2":"⬆️","down2":"⬇️",
    "info2":"©️","link2":"🔗","search":"🔍","boom":"💥","sparkle2":"✨","diamond2":"💵",
    "money":"💱","lightning":"⚡️","brain":"🧠","skull":"💀","ghost":"👻",
    "clown":"🤡","robot":"🤖","one":"1️⃣","two":"2️⃣","three":"3️⃣",
}

# Additional IDs supplied from Telegram iOS Icons, @rijif and Boseh packs.
# Keys are kept pack-specific so existing logical icons stay stable. Call pe(key)
# to render these, or receive their Unicode fallback when custom emoji is unavailable.
ADDITIONAL_EMOJIS: dict[str, tuple[str, str]] = {
    # Telegram iOS Icons
    "ios_plane": ("✈️", "6028346797368283073"),
    "ios_apple": ("🍏", "5775870512127283512"),
    "ios_star": ("⭐️", "6028338546736107668"),
    "ios_star_alt": ("⭐️", "5767199127775481841"),
    "ios_gift": ("🎁", "5773677501825945508"),
    "ios_symbols": ("🔣", "6035162669948867129"),
    "ios_computer": ("🖥", "5942734685976138521"),
    "ios_gear": ("⚙️", "5904258298764334001"),
    "ios_controls": ("🎛", "5776424837786374634"),
    "ios_newspaper": ("📰", "5895519358871932592"),
    "ios_memo": ("📝", "5920046907782074235"),
    "ios_archive": ("🗂", "5766994197705921104"),
    "ios_arrows": ("↔️", "5893316448670978477"),
    "ios_repeat": ("🔁", "6030657343744644592"),
    "ios_edit": ("✏️", "6039779802741739617"),
    "ios_keyboard": ("⌨", "6039404727542747508"),
    "ios_paperclip": ("📎", "6039451237743595514"),
    "ios_hammer": ("🔨", "5940433880585605708"),
    "ios_door": ("🚪", "6035130900075777681"),
    "ios_search": ("🔎", "6032850693348399258"),
    "ios_tag": ("🏷", "5888620056551625531"),
    "ios_reply": ("↩️", "5895507195524550741"),
    "ios_right": ("➡️", "5895383238473421210"),
    "ios_tv": ("📺", "6039391078136681499"),
    "ios_link": ("🔗", "6030864215139422409"),
    "ios_add": ("➕", "6032924188828767321"),
    "ios_info": ("ℹ", "6028435952299413210"),
    "ios_question": ("❓", "6030848053177486888"),
    "ios_exclaim": ("❗️", "6030563507299160824"),
    "ios_play": ("▶️", "5773626993010546707"),
    "ios_close": ("❌", "6030757850274336631"),
    "ios_check": ("✅", "5774022692642492953"),
    "ios_up": ("⬆️", "6028205772117118673"),
    "ios_lock": ("🔒", "6037249452824072506"),
    "ios_image": ("🖼", "6030466823290360017"),
    "ios_folder": ("📁", "6037475557082403885"),
    "ios_file": ("📄", "6034969813032374911"),
    "ios_trash": ("🗑", "6039522349517115015"),
    "ios_eye": ("👁", "6037397706505195857"),
    "ios_down": ("⬇️", "6037157012242960559"),
    "ios_cloud": ("☁", "6028115612163641653"),
    "ios_upload": ("📤", "6039573425268201570"),
    "ios_shield": ("🛡", "6030537007350944596"),
    # @rijif pack
    "rijif_warning": ("⚠️", "5039665997506675838"),
    "rijif_forbid": ("🚫", "5039671744172917707"),
    "rijif_heart_fire": ("❤️‍🔥", "5042225965518816316"),
    "rijif_gift": ("🎁", "5041975203853239332"),
    "rijif_cool": ("🆒", "5039686583284925280"),
    "rijif_champagne": ("🥂", "5039774728898741491"),
    "rijif_bell": ("🔔", "5042111805288089118"),
    "rijif_location": ("📍", "5039775669496579510"),
    "rijif_ok": ("🆗", "5042020176455795565"),
    "rijif_tree": ("🎄", "5039670898064360513"),
    "rijif_snowman": ("☃️", "5039936198194234403"),
    "rijif_cookie": ("🍪", "5040071919160788440"),
    "rijif_sled": ("🛷", "5042298743739647195"),
    "rijif_stone": ("🗿", "5040045238823945201"),
    "rijif_disco": ("🪩", "5039670228049462451"),
    "rijif_elf": ("🧝", "5039531487720899631"),
    "rijif_speech": ("🗣️", "5039643534827717738"),
    "rijif_blue_heart": ("💙", "5039560388555834382"),
    "rijif_thumbs_up": ("👍", "5039544445637231745"),
    "rijif_hundred": ("💯", "5042297717242463211"),
    "rijif_black_bird": ("🐦‍⬛️", "5041866884778034602"),
    "rijif_party": ("🎉", "5039778134807806727"),
    "rijif_megaphone": ("📣", "5041888071851705019"),
    "rijif_rainbow": ("🌈", "5041955142060999726"),
    "rijif_pause": ("⏸", "5042036407137207122"),
    "rijif_search": ("🔍", "5039649904264217620"),
    # Boseh / NewEmojis pack
    "boseh_purple_heart": ("💜", "5084974483685507801"),
    "boseh_paw_prints": ("🐾", "5084923566848213749"),
    "boseh_butterfly": ("🦋", "5084613633418199991"),
    "boseh_battery_low": ("🪫", "5084813564145828384"),
    "boseh_guitar": ("🎸", "5116416491855545424"),
    "boseh_sleep": ("💤", "5116590266232341370"),
    "boseh_gamepad": ("🎮", "5116175844837950263"),
    "boseh_speaker_mute": ("🔇", "5116466579764151159"),
    "boseh_person": ("👤", "5116582462276764538"),
    "boseh_video": ("🎥", "5118744200921219799"),
    "boseh_clock": ("⏰", "5123230779593196220"),
    "rijif_telephone": ("📞", "5172893417717367746"),
    "rijif_mouse": ("🖱️", "4918408122868958076"),
    "rijif_camera": ("📷", "4918159650420950146"),
}
for _alias, (_fallback, _emoji_id) in ADDITIONAL_EMOJIS.items():
    PREMIUM_IDS[_alias] = _emoji_id
    FALLBACK[_alias] = _fallback

# Full numbered catalogs supplied by the user. Numbered aliases preserve every
# variant (including duplicate glyphs) so all IDs can be checked via /emojiinfo
# and selected explicitly with pe("tgiosicons_001"), pe("vector_001"), etc.
# Format per row: Unicode fallback followed by the exact Telegram emoji ID.
SUPPLIED_EMOJI_PACKS: dict[str, str] = {
    "tgiosicons": """
✈️ 6028346797368283073
🍏 5775870512127283512
⭐️ 6028338546736107668
⭐️ 5767199127775481841
🎁 5773677501825945508
🔣 6035162669948867129
🖥 5942734685976138521
⚙️ 5904258298764334001
⚙ 6032742198179532882
⚙️ 5850309953293653168
⚙️ 5850332476102153487
⚙️ 5850392884817172292
⚙️ 5850224242926295392
⚙️ 5924722061288150929
🎛 5776424837786374634
🎛 5771449289972650710
📰 5895519358871932592
📰 5893444447286334441
📰 5886437972647088483
📰 5893236738372932548
📰 5893057118545646106
📝 5920046907782074235
📝 5922693616953725714
🗂 5766994197705921104
↔️ 5893316448670978477
↔️ 5895534923833413814
⬅️ 5960671702059848143
🔁 6030657343744644592
⏫ 5938437708635443119
✏️ 6039779802741739617
✏ 6039614175917903752
❌ 6030757850274336631
⌨ 6039404727542747508
📎 6039451237743595514
🔧 5962952497197748583
🔨 5940433880585605708
🚪 6035130900075777681
🔎 6032850693348399258
🏷 5888620056551625531
🏷 5886285355279193209
🏷 5884050696679986441
🏷 5884090188904272855
🏷 5886473311637999700
🏷 5888880224195581055
🏷 5884491244360438851
↩️ 5895507195524550741
⬅️ 6039539366177541657
➡️ 5895383238473421210
➡️ 6037622221625626773
📺 6039391078136681499
🔗 6028171274939797252
🔗 6030864215139422409
🔗 5776078972659962594
🔗 5778455936410588193
🔗 5895364284782743985
🔗 5769289093221454192
🔗 5766902139376898645
➕ 6032924188828767321
ℹ 6028435952299413210
❓ 6030848053177486888
❗️ 6030563507299160824
▶️ 5773626993010546707
▶️ 5850346984501680054
❌ 5774077015388852135
✅ 5774022692642492953
⬆️ 6028205772117118673
🔓 6037496202990194718
🔒 6037249452824072506
🖼 6030466823290360017
🖼 6035128606563241721
🤖 6030400221232501136
⭐️ 6030425896546996257
⭐️ 6030680867280522811
📁 6037475557082403885
📁 5904219717073114606
📄 6034969813032374911
🗑 6039522349517115015
🎶 6037364759811068375
🎶 6037460610596212193
👁 6037397706505195857
👁 6037243349675544634
👁 5884097155341226387
👁 5935757052042285202
⬇️ 6037157012242960559
⬇️ 5884218166044791498
⬇️ 6039802767931871481
☁ 6028115612163641653
⬇️ 6032745346390560408
⬆️ 5963103826075456248
⬇️ 5963087934696459905
⬆️ 6039391666547201160
📤 6039573425268201570
⬆️ 5776288820467077551
🛡 6030537007350944596
🛡 6032636795387121097
🛡 6030445631921721471
📂 6039630677182254664
📂 6039800856671424701
📂 6037373985400819577
📂 6039348811363520645
""",
    "vector": """
✅ 5219899949281453881
🎶 5222472119295684375
✨ 5222108309795908493
❄️ 5219672809936006424
🐾 5244820603663296299
⚡ 5219943216781995020
💔 5222400230133081714
🔥 5222148368955877900
💥 5219901967916084166
♨️ 5260424249914435335
💯 5222241728659988366
🚫 5219805369806629055
🤥 5219866135003933502
❗ 5220197908342648622
❓ 5220053623211305785
🔝 5246794802560774143
✈️ 5217890643321300022
©️ 5247213725080890199
®️ 5246863809800318186
🔧 5258023599419171861
👀 5220070652756635426
💼 5246942081284320100
✍️ 5220046725493828505
👾 5303396278179210513
✅ 5276489300207217985
🆕 5294524383279198295
🔵 5294096239464295059
🔇 5278619986238122736
✈️ 5364174510708764528
👻 5258456562187381288
👻 5294527084813626369
🌟 5294017134756636818
✈️ 5332423642850536254
💎 5264892613630111886
☝️ 5301096984617166561
〰️ 5301275719681190738
⭐ 5310224206732996002
🌙 5377377257356537351
🙈 5294363352070367389
🧠 5314413943035278948
⭐ 5386521874089914548
🏳️ 5397730656400714154
✅ 5465542769755826716
🎲 5235588635885054955
🦋 5289862389552919154
🎵 5334665104677941170
💤 5334811859415477124
🔄 5292226786229236118
🎱 5289940334619406906
🕷️ 5335005820138564214
✍️ 5289930378885214069
🔋 5391118489824015979
🔒 5393302369024882368
🥷 5391034312759980875
🔔 5431374840332302296
🪙 5237761614458933049
🧃 5258391003806584549
🥂 5258389638006984449
🍷 5257961116234958730
🥃 5258056717912000584
🛒 5258024802010026053
⌛ 5258113901106580375
🎈 5258212320282168974
🔍 5258274739041883702
🔎 5258396243666681152
❓ 5258387666616994756
🎥 5258217809250372293
💤 5258077595748030166
🔄 5258281774198311547
💋 5258421738592553935
💱 5258296359907249075
👾 5258196742435787040
✈️ 5258466470676940666
✈️ 5258079378159453410
📀 5258234027046883085
🎤 5258500422393415126
🐈 5257987903945986017
⭐ 5258039825805624495
💡 5258466217273871977
🦖 5258121851091043775
🚁 5258450231405595367
🪙 5283232570660634549
🟢 5339135753316222622
✋ 5339286072876614251
⛔ 5339233635620899144
⭐ 5341601055954194475
⭐ 5341684837881235158
💣 5341570033405412393
💀 5357592447557848986
💎 5343636681473935403
📂 5341492148468465410
🎄 5343777912883529222
🕸️ 5341357711697134290
🐶 5364052602357044385
🥸 5454371323595744068
🐞 5452051336881271172
⭐ 5453900977432188793
⭐ 5453969572354878595
💱 5454409660473827001
📞 5453965363286925977
💕 5454365405130810498
❤️ 5454249887690415056
🔑 5454386656628991407
🔄 5452002073606384268
💻 5454079785510660283
🐆 5454206993852029667
☝️ 5454360341364363439
🎥 5454156248813432363
✈️ 5454245266305604993
🔄 5454074580010295588
🎆 5454345339043601366
🍹 5454232969814238500
💣 5454225015534805938
🗡️ 5454172148782359440
⚔️ 5453991094435997597
🐈‍⬛ 5453976908159016299
📎 5454419255430767770
🚩 5454310635707853545
""",
}
for _pack, _rows in SUPPLIED_EMOJI_PACKS.items():
    for _index, _row in enumerate(_rows.strip().splitlines(), start=1):
        _fallback, _emoji_id = _row.rsplit(maxsplit=1)
        _alias = f"{_pack}_{_index:03d}"
        PREMIUM_IDS[_alias] = _emoji_id
        FALLBACK[_alias] = _fallback


def tg_emoji(emoji_id: str | int, fallback: str = "✨") -> str:
    """Return <tg-emoji> HTML if premium enabled, else fallback glyph."""
    fallback = html.escape(str(fallback))
    if not USE_PREMIUM or not re.fullmatch(r"[1-9][0-9]{0,18}", str(emoji_id)) or int(emoji_id) > 9223372036854775807:
        return fallback
    # Bot API supports <tg-emoji emoji-id="...">emoji</tg-emoji>
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

def pe(key: str, fallback: str | None = None) -> str:
    """Premium emoji by logical key — auto falls back to cyber glyph."""
    fid = PREMIUM_IDS.get(key, "")
    # An empty legacy fallback means "use the canonical Unicode fallback", not
    # an empty custom-emoji entity (which Telegram cannot render).
    fb = fallback or FALLBACK.get(key, "✨")
    return tg_emoji(fid, fb)

# ── Ready-made cyber helpers — drop-in replacements for formatters.CYBER ──
def orb() -> str:     return pe("orb", "◍")
def diamond() -> str: return pe("diamond", "⬪")
def line() -> str:    return pe("line", "⫶")
def small() -> str:   return pe("small", "⬩")
def spark() -> str:   return pe("spark", "𖦹")
def circle() -> str:  return pe("circle", "⦿")
def target() -> str:  return pe("target", "◎")
def hexg() -> str:    return pe("hex", "⬢")
def arrow() -> str:   return pe("arrow", "➪")

# For headers — premium line
def header_emoji() -> str:
    # Use orb + diamond + spark combo
    return f"{orb()} {diamond()}"

# Expose all IDs for /premium debug command
def list_all() -> dict[str, str]:
    return PREMIUM_IDS.copy()
