# Production cleanup

Removed only inactive source, checked against ALL_MODULES, PROFESSIONAL_PLUGINS and source imports. Shared runtime, MongoDB data, streaming code, credentials and licensed vendors are retained.

Removed 69 files:

- `videl/plugins/anilist.py`
- `videl/plugins/antibot.py`
- `videl/plugins/anime_search.py`
- `videl/plugins/antiflood_pro.py`
- `videl/plugins/antiraid.py`
- `videl/plugins/approve_pro.py`
- `videl/plugins/automod.py`
- `videl/plugins/backup.py`
- `videl/plugins/birthdays.py`
- `videl/plugins/blacklist_pro.py`
- `videl/plugins/calculator.py`
- `videl/plugins/captcha_pro.py`
- `videl/plugins/carbon.py`
- `videl/plugins/character.py`
- `videl/plugins/connect.py`
- `videl/plugins/couples.py`
- `videl/plugins/covid.py`
- `videl/plugins/dare.py`
- `videl/plugins/dice.py`
- `videl/plugins/economy.py`
- `videl/plugins/emojify.py`
- `videl/plugins/fact.py`
- `videl/plugins/ghost.py`
- `videl/plugins/gimme.py`
- `videl/plugins/github.py`
- `videl/plugins/goodbye_pro.py`
- `videl/plugins/insta.py`
- `videl/plugins/joke.py`
- `videl/plugins/kang.py`
- `videl/plugins/karma.py`
- `videl/plugins/level.py`
- `videl/plugins/logpro.py`
- `videl/plugins/manga.py`
- `videl/plugins/math.py`
- `videl/plugins/memepro.py`
- `videl/plugins/neko.py`
- `videl/plugins/nsfw_gate.py`
- `videl/plugins/pinpro.py`
- `videl/plugins/pinterest.py`
- `videl/plugins/purgepro.py`
- `videl/plugins/qrgen.py`
- `videl/plugins/quiz.py`
- `videl/plugins/quotepro.py`
- `videl/plugins/reaction.py`
- `videl/plugins/report.py`
- `videl/plugins/selfies.py`
- `videl/plugins/ship.py`
- `videl/plugins/shortener.py`
- `videl/plugins/spamwatch.py`
- `videl/plugins/speedtest.py`
- `videl/plugins/statspro.py`
- `videl/plugins/stickerpro.py`
- `videl/plugins/sysinfo.py`
- `videl/plugins/tiktok.py`
- `videl/plugins/tograph.py`
- `videl/plugins/trending.py`
- `videl/plugins/truth.py`
- `videl/plugins/urban.py`
- `videl/plugins/vault.py`
- `videl/plugins/waifu.py`
- `videl/plugins/wallpaper.py`
- `videl/plugins/warnpro.py`
- `videl/plugins/weather.py`
- `videl/plugins/welcome_pro.py`
- `videl/plugins/wiki.py`
- `videl/plugins/zimage.py`
- `videl/modules/elite_pro.py`
- `videl/modules/dashboard_sync.py`
- `webapp/src/components/chat/ChatView.tsx`

## Follow-up: lean command and dependency surface

This pass removed 37 command names (185 → 148 registered names, including aliases):
- Demo/showcase `/buttons` and `/features`; actual styled buttons and Richgram stay.
- Raw `/logs` and `/log` delivery; server logging and error persistence stay.
- Redundant aliases for lyrics, channel setup, vote-skip settings, playlists,
  downloads, approvals and blacklist controls; canonical handlers stay.
- `/sys` alias; private owner `/sysinfo` stays. Common `/q` and `/setup` stay.

See `tests/test_command_cleanup.py` for the explicit retired-name set and
`docs/COMMAND_REFERENCE.md` for the complete remaining set. Menu entries and
public help were updated. Already-sent functional callbacks remain compatible.

Removed unused dependencies: Beautiful Soup, lxml, QR code/barcode generators,
URL shortener and Google TTS. Removed the unused static config help map that
advertised retired utilities, nonfunctional paid/business/checklist/direct-message
feature switches, old ping-image setting and unused cyber-theme deployment flag.
`/repo` now links to the correct Videl0 source/licenses without hosting promotions
or duplicate source/fork buttons. MIT notices and vendor credits remain intact.

Also corrected retained `/song`, `/vsong`, `/download` filters: group AND private
was impossible; they now accept group OR private messages. This filter fix is
unit-tested, not evidence of a live successful download.

No database documents, playlists, drafts, cookies, media, environment files or
license files were deleted by this cleanup. Production rollout remains pending.
